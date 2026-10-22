from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages, abort
from datetime import datetime, timedelta
import json, datetime, sqlite3, re
import time
import os
import sys

# create flask web app
app = Flask("__name__")
app.secret_key = "your-secret-key"

# functions
def load_data_products():
    with open("data/products.json") as product:
        return json.load(product)


def load_data_coupons():
    with open("data/coupons.json") as cpn:
        return json.load(cpn)


def initialise_database():
    # ORDER HISTORY
    with sqlite3.connect("order_history.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    customer TEXT NOT NULL,
                    items TEXT NOT NULL,
                    subtotal REAL,
                    gst REAL,
                    ship_fee FLOAT,
                    discount FLOAT,
                    total_charges REAL,
                    items_on_hold TEXT
                    )
        """)

    # ACCOUNTS
    with sqlite3.connect("accounts.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    items TEXT,
                    wishlists TEXT,
                    billing_info TEXT,
                    applied_coupon TEXT,
                    used_coupons TEXT
                    )
        """)


def logger(types: str = "ERROR", cause = None, sector = "error"):
    """Display error message on terminal output in coloured variants.

    Parameters:
    |   types in string ("ERROR" in default)
    |   statement cause (None in default)
    |   sector or areas in displaying different coloured texts

    """
    if sector == "error":
        print(f"\33[1m\33[91m{types}{f": \33[0m\33[35m{cause}\33[0m" if cause else ""}")

    elif sector == "warning":
        print(f"\33[33m{types}{f": \33[0m\33[3m\33[34m{cause}\33[0m" if cause else ""}")

    elif sector == "closed_log":
        print(f"\33[2m{cause}\33[0m")


def update_stock(item: dict):
    """Update the stock of the following product items.

    Then, append the calls of each of reserved items
    when they are pre-released, exceeded the stock
    limit, or run out of stock.

    In pre-order cycle, they can be stacked with their
    conjunctive terms ("out_of_stock" in list,
    -yet_suspended in string) when they have a stock related
    issues like exceeded (reaching beyond 0) or
    ordering an item that is out of stock.

    Parameters:
    |   album products (dict), as cart

        product_name: {
            '...': '...'
        }, ...

    Returns:
        listed calls in dict for each reserved items

    """
    reserved = {}  # on partial fulfillment or backorder

    with open("data/products.json", "r") as product:
        fetched_album_data = json.load(product)

    for album_name, i in item.items():
        if album_name in fetched_album_data:
            pile_cycle = False
            album_module_cycle = check_date(i, 1)

            # pre-released orders are subjected to change too / limiting the number or pre-orders on that product
            fetched_stock = fetched_album_data[album_name]["stock"]
            fetched_stock -= i["quantity"]  # modify the stock

            if album_module_cycle == "pre-released":  # pre-release items
                calls = "before_released"
                demand_cause = "pre_order"

                pile_cycle = True

            # prompt when stock reached 0 or beyond
            if fetched_stock < 0:
                calls = "suspended"

                # out of stock measurement
                if fetched_stock <= -1 * i["quantity"]:
                    if pile_cycle:
                        demand_cause = ["pre_order", "out_of_stock"]
                        calls = "before_released_yet_suspended"
                    else:
                        demand_cause = "out_of_stock"

                # quantity demand exceeded the stock inventory
                else:
                    if pile_cycle:
                        demand_cause = ["pre_order", "exceeded"]
                        calls = "before_released_yet_suspended"
                    else:
                        demand_cause = "exceeded"

                fetched_stock = 0

            # dictionary append
            if fetched_album_data[album_name]["stock"] - i["quantity"] < 0 or pile_cycle:
                reserved[album_name] = {
                    "id": i["id"],
                    "artist": i["artist"],
                    "name": album_name,
                    "call": calls,
                    "cause_of_demand": demand_cause,
                    "demand_tracking": f"limit: {fetched_album_data[album_name]["stock"]} | demand: {i["quantity"]}",
                    "quantity_demand": i["quantity"]
                }

            # change the stock inventory
            fetched_album_data[album_name]["stock"] = fetched_stock

    with open("data/products.json", "w") as product:
        json.dump(fetched_album_data, product, indent=4)

    return reserved


def streamlined_demand(rsv):
    """Use the reserved items to display the side panel.

    This relies on going through cause of demands
    key in each of product items in dictionary.

    The process intake is either partial fulfillment
    or backorder process.

    Parameters:
    |   reserved items (dict)

    Returns:
        original parameter of rsv, or {} if exception
    """
    with sqlite3.connect("order_history.db") as conn:
        try:
            # first, it checks for existing column
            cursor = conn.cursor()
            cursor.execute(f"SELECT items_on_hold FROM orders")
            stock_related_cause = {}

            for n in rsv.keys():
                if "pre_order" not in rsv[n]["cause_of_demand"]:
                    stock_related_cause[n] = rsv[n]

            # building the side panel template
            if stock_related_cause:
                flash("%.show_panel_3;")
                flash(rsv)  # critical for side panel key access

            return rsv

        except (sqlite3.Error, KeyError):
            return {}  # skip storing reserved items to the database


def verify_existing_product(loaded_albums: dict, val: dict, target: str, allow_change=True):
    """Verify if the product in cart/wishlist is exists.

    it is used to overcome throwing KeyError when music
    album is assumed to be missing and mismatched catalogue
    id.

    e.g. 'dict object' has no attribute
    'The Key To Withstand' (over 'The Key To Withtand')

    """
    new_value = {}
    strike = 0

    for album_name, v in val.items():
        # if the name within 'val' is not found
        if not loaded_albums.get(album_name):
            strike += 1

            for n, uv in loaded_albums.items():
                if uv["id"] == v["id"]:
                    new_value[n] = v  # change the name
                    break
            else:
                new_value[album_name] = v
                new_value[album_name]["is_unavailable"] = True

        # name in cart/wishlist is exist, but the id is mismatched
        elif v["id"] != loaded_albums[album_name]["id"]:
            new_value[album_name] = v
            new_value[album_name]["id"] = loaded_albums[album_name]["id"]
            strike += 1

        else:
            new_value[album_name] = v

            if "is_unavailable" in v:
                new_value[album_name].pop("is_unavailable")

    if strike > 0 and allow_change:
        if target == "cart":
            save_entries(cart=new_value)
        elif target == "wishlists":
            save_entries(wishlists=new_value)

        return new_value

    return val


def discriminate(ry: str):
    """Determine the variety of terms with their difference.

    Parameters:
    |   "ry" column name (string)

    Return a column key and session key name.
    <term>, <term-key-session>

    If there is no difference between them, then return the
    same, original parameter.

    """
    if ry == "cart":
        return "items", "cart"
    elif ry == "coupon":
        return ["applied_coupon" for _ in range(2)]

    return [ry for _ in range(2)]


# syntax building for database
def set_syntax_building(argument: dict | list | tuple, positional_value: list|tuple = ()):
    """Build a syntax for preparing a database saving action.

    Parameters: 
        argument // (dict|list|tuples) column name on database
        positional values // (list|tuple) using values to modify

    Returns:
        structured syntax SQL (list) containing like '<column> = ?'
        syntax values to modify data (list)
        modified session_keys (dict)

    """
    def initialise_build(params: dict):
        if type(params) is not dict:
            raise TypeError(f"The argument or the parameter to initialising 'set' syntax structure is not in dict; got {type(params)}")

        key_terms = ["cart", "wishlists", "billing_info", "applied_coupon", "coupon", "used_coupons"]
        session_key = session.get("session_key", {})

        set_clause_structure = []
        set_clause_value = []

        for tr in params.keys():
            if tr in key_terms:
                # variant words or terms: cart/items, coupon/applied_coupon
                term, term_key_session = discriminate(tr)

                # set syntax building prompt
                set_clause_structure.append(f"{term} = ?")
                set_clause_value.append(json.dumps(params[tr]))

                # non-existent session keywords
                if tr != "wishlists" or tr != "billing_info":
                    session_key[term_key_session] = params[tr]

        # finalising prompt
        return set_clause_structure, set_clause_value, session_key

    storer = {}

    # *args
    if type(argument) is tuple or type(argument) is list:
        # verify if both argument and positional values were the same amount of items
        if len(argument) != len(positional_value):
            raise AssertionError(f"The amount of value it has, as a list for positional value, must have the same value as the amount of key argument has: {len(argument)} | {len(positional_value)}")
        
        # adding to storer dictionary via for-loop
        for j in range(len(argument)):
            storer[argument[j]] = positional_value[j]
        
    # **kwargs
    elif type(argument) is dict:
        storer = argument

    else:
        logger(False, f"INVALID TYPE: must be dict, list or tuple but got {type(argument)}", "closed_log")
        raise TypeError(f"Main argument is an invalid type ({type(argument)}); it requires to be at dictionary, list, or tuple.")

    # two returned lists of 'set' syntax: structure, value & one for session_key configuration
    return initialise_build(storer)


def make_change_to_database(syntax_structure: list, syntax_val: list, key_session):
    """Update a column value to the database of a currently logged on account.

    Parameters:
    |   syntax structure (from set_syntax_building function)
    |   syntax values (from set_syntax_building function)
    |   modified key session

    Returns:
        status (success, or fail on errors)

    """
    session_key = session.get("session_key", {})

    # updating database table
    with sqlite3.connect("accounts.db") as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE accounts
                SET {", ".join(syntax_structure)}
                WHERE email = '{session_key["email"]}'
            """, tuple(syntax_val))

            session["session_key"] = key_session
            session.modified = True

            conn.commit()

            # successful saving action
            return {
                "is_saved": "database",
                "status": 1
            }

        except sqlite3.Error as make_changes_error:
            conn.rollback()
            logger("SAVE DATABASE ERROR", make_changes_error)

            # unsuccessful saving action due to exception
            return None


# use 'get_entry' function when dealing with two sides
def get_entry(*args):
    """Fetch the value with the appropriate name of the session/column.

    Strict Searching in registered accounts
    requires the name to be listed under
    existing columns from database accounts.

    Parameters *args:
    |   name of the session/column

    Returns:
    |   value from session.get // looping to get data

    """
    try:
        result = []  # fetched keywords
        has_session_key = session.get("session_key", {})

        # guest account
        if not has_session_key:
            for tg in args:
                v = session.get(tg, {})
                result.append(v)

        # session with user being logged on
        else:
            with sqlite3.connect("accounts.db") as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM accounts WHERE email = '{has_session_key["email"]}'")

                post_identifier = cursor.fetchall()
                main_row = post_identifier[0]
                ttr = {
                    "items": json.loads(main_row[5]),
                    "wishlists": json.loads(main_row[6]),
                    "billing_info": json.loads(main_row[7]),
                    "applied_coupon": json.loads(main_row[8]),
                    "used_coupons": json.loads(main_row[9]),
                }

                for tr in args:
                    # preparing items to be delivered
                    try:
                        term, _ = discriminate(tr)

                        if term in ttr.keys():
                            rar = ttr[term]
                        else:
                            rar = {}

                        result.append(rar)

                    except:
                        result.append({})

    except Exception as get_whole_error:
        logger("FETCH WHOLE ERROR:", get_whole_error)
        result = [{} for _ in args]

    return result[0] if len(args) == 1 else result


def save_entries(**kwargs):
    """Save values either on session or database.

    Parameters **kwargs:
    |   name of the <key> in dictionary
    |   the <value> for the key
    |
    |   {column1: key1, ...}

    action:
        (guest) session[column] = value //
        (registered) save through database

    Returns:
        status (either boolean or dict version) unless exception

    """
    try:
        has_session_key = session.get("session_key", {})

        # guest
        if not has_session_key:
            for tg, value in kwargs.items():
                session[tg] = value

            session.modified = True  # finalising by saving the session
            return {
                "is_saved": "session",
                "status": 1
            }

        # session with user being logged on
        else:
            syntaxes, stx_value, session_key = set_syntax_building(kwargs)
            return make_change_to_database(syntaxes, stx_value, session_key)

    except Exception as save_error:
        logger("SAVE ERROR", save_error)
        flash(f"An error occurred while attempting to save configuration.")


def remove_specific_key(**kwargs):
    """Delete a specific key on dictionary.

    Parameters **kwargs:
    |   name of session/column
    |   name of the key ()
    |
    |   {column1: key1, ...}

    action:
        del session/column[key]

    Returns:
        status (success in dict, False)
    """
    try:
        has_session_key = session.get("session_key", {})

        # guest
        if not has_session_key:
            for session_name, key in kwargs.items():
                vs = session.get(session_name, {})
                del vs[key]

                session[session_name] = vs

            session.modified = True
            return {
                "is_saved": "session",
                "status": True
            }

        # session with user being logged on
        else:
            vts = []  # value to save, stored after a "del" action

            with sqlite3.connect("accounts.db") as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM accounts WHERE email = '{has_session_key["email"]}'")

                p = cursor.fetchall()
                main_row = p[0]

                items = json.loads(main_row[5])
                wishlists = json.loads(main_row[6])
                billing_info = json.loads(main_row[7])
                applied_coupon = json.loads(main_row[8])
                used_coupons = json.loads(main_row[9])

                for column, key in kwargs.items():
                    if column == "cart":
                        del items[key]
                        vts.append(items)

                    elif column == "wishlists":
                        del wishlists[key]
                        vts.append(wishlists)

                    elif column == "billing_info":
                        del billing_info[key]
                        vts.append(billing_info)

                    elif column == "applied_coupon" or column == "coupon":
                        del applied_coupon[key]
                        vts.append(applied_coupon)

                    elif column == "used_coupons":
                        del used_coupons[key]
                        vts.append(used_coupons)

            columns = tuple(kwargs.keys())
            syntaxes, stx_value, session_key = set_syntax_building(columns, vts)
            return make_change_to_database(syntaxes, stx_value, session_key)

    except Exception as remove_key_error:
        logger("REMOVE SPECIFIC KEY(S) ERROR", remove_key_error)
        flash(f"An error occurred while attempting to remove specific key(s).")

        return None  # unsuccessful deletion of specific key


def remove_key(*args):
    """Replace a dictionary data with an empty value {}.

    Parameters *args:
    |   name of session/column

    action:
        (guest) pop the key name of session
        (registered) saved with empty {} through database

    """
    try:
        has_session_key = session.get("session_key", {})

        # guest
        if not has_session_key:
            for session_name in args:
                session.pop(session_name, None)

            session.modified = True
            return {
                "is_changed": "session",
                "status": True
            }

        # session with user being logged on
        else:
            syntaxes, stx_value, session_key = set_syntax_building(args, ({},) * len(args))
            return make_change_to_database(syntaxes, stx_value, session_key)

    except Exception as delete_error:
        logger("DELETE ERROR", f"An error occurred while attempting to make configuration. {delete_error}")
        return None  # unsuccessful pop deletion

# -----------------------------------------------------------------------------------

def signin_session(email, password, msr=0):
    """Apply a session key when user is signing up or logging in.

    Conditions:
    |   (login) password is identical to stored user's password on database

    Parameters:
    |   email (string)
    |   password (validated on login only)
    |   "msr": method (int)
    """
    with sqlite3.connect("accounts.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM accounts WHERE email = '{email}'")

        # check for an account associated with email
        post_identifier = cursor.fetchone()

        if post_identifier:
            uid = post_identifier

            # initials
            retrieved_item = json.loads(uid[5])
            retrieved_coupon = None
            retrieved_used_coupons = None

            # log in method
            if msr == 1:
                if password != uid[4]:  # not matched
                    raise ValueError("Password is incorrect")

                # retrieving the column values
                retrieved_coupon = json.loads(uid[8])
                retrieved_used_coupons = json.loads(uid[9])

            # In-Session Key in dict (accessed account)
            session_key = session.get("session_key", {})
            session_key = {
                "user_id": uid[0],
                "name": uid[2],
                "email": email,
                "cart": retrieved_item,
                "accessed": True,
                "applied_coupon": retrieved_coupon,
                "used_coupons": retrieved_used_coupons
            }

            session["session_key"] = session_key  # define the session key
            session.modified = True

        else:
            # empty post_identifier; not found
            raise NameError(f"{email} is not found. Try double checking your email.")


def calculate_total(c):
    """Calculate the main price from items in cart.

    This involves selecting the price by the quantity of
    its processed item to calculate the subtotal.

    GST is added as a surcharge of 15%.

    Delivery fee is determined by the subtotal price boundary.

    Discount is included when user has applied a valid coupon.

    Parameters:
    |   cart (dict)

    Returns:
    |   main total,
    |   subtotal,
    |   GST,
    |   delivery/shipping fee (if possible),
    |   discount value (if possible)
    |   total with discount // main total

    """
    def get_shipping_fee(cart_total):
        # Shipping Fee: Determined by subtotal
        if cart_total > 200:
            return 5.3
        elif 200 >= cart_total > 100:
            return 2.7

        return 0  # initial

    def get_total_with_discount(main_total):
        t = 0
        has_coupon_applied = get_entry("coupon")

        # get the total with the discount
        if has_coupon_applied != {}:
            discount = has_coupon_applied["discount"]

            # determination by value
            if discount > 1:  # via regular whole number
                t = main_total - discount
            elif discount <= 1:  # via percentage
                t = main_total - (main_total * discount)

            # reached below zero (negative)
            if t < 0:
                t = 0

            return discount, t

        # as original value
        return 0, main_total

    # round() rule to prevent math float inaccuracy
    cart_total = round(sum((item["price"] * item["quantity"]) for item in c.values()), 2)
    gst = round(cart_total * 0.15, 2)
    shipping_fee = get_shipping_fee(cart_total)

    # calculate for total
    main_total = cart_total + gst + shipping_fee

    # get discount via session
    discount_value, tl_w_disc = get_total_with_discount(main_total)

    return main_total, cart_total, gst, shipping_fee, discount_value, tl_w_disc


def remove_coupon_action():
    """Remove a coupon from the user.

    Returns:
        status (success, fail on removal failure or exception)

    """
    try:
        cpn_name = get_entry("coupon")["name"]  # get the dict value first, then the coupon name
        removal_status = remove_key("coupon")

        status = {
            "removed_cpn_name": cpn_name
        }

        return status if removal_status else None

    except KeyError:
        return None


def spike_used_coupon(cpn):
    """Add an applied coupon to a used coupon."""
    set_used_coupons = get_entry("used_coupons")

    try:
        if cpn:
            coupon_name = cpn["name"]

            # None as a placeholder since
            # there is nothing to access their value
            set_used_coupons[coupon_name] = None
            save_entries(used_coupons=set_used_coupons)

    except KeyError:
        logger(False, "Unable to add coupon to used coupons", "closed_log")


def coupon_validity():
    """Validate whether an applied coupon still exists."""
    try:
        coupon = get_entry("coupon")

        if coupon:
            cpn_name = coupon["name"]
            get_data_coupon = load_data_coupons()

            # invalid coupon
            if cpn_name not in get_data_coupon:
                remove_coupon_action()

                flash(f"The coupon you have, {cpn_name}, is no longer valid.")

            # dissimiliar discount value
            elif coupon["discount"] != get_data_coupon[cpn_name]["discount"]:
                coupon["discount"] = get_data_coupon[cpn_name]["discount"]

                save_entries(coupon=coupon)

    except Exception as validate_coupon_error:
        logger(False, f"Failed to validate coupon: {validate_coupon_error}", "closed_log")


def item_display_by_genre(gnr: str = None, px_range: str = None):
    """Get the product items by a specified genre, alongside with an optional price range.

    This evaluates the genre of a processed product items,
    alongside the price range filtering.

    Parameter:
    |   genre (str; default is None) to select only items
    |   pxrange (str; default is None) alongside the price range

    actions:
    |   adds the selected item via matching genre.
    |   'io' counts when product genre through for-loop
        is matched to a specified genre.

    Returns:
        (ordinary returns) selected item

        (with filters of price range)
        |   io (int)
    """
    # checking their price range
    def check_price_range(ap):
        # if-else condition via price (px) range
        if px_range is None:
            return True  # None to proceed
        elif px_range == "below_15":
            return ap < 15
        elif px_range == "15_to_30":
            return 15 <= ap <= 30
        elif px_range == "30_to_50":
            return 30 <= ap <= 50
        elif px_range == "50_to_100":
            return 50 <= ap <= 100
        elif px_range == "above_100":
            return 100 < ap
        else:
            return False

    c = get_entry("cart")
    stored_data = {}  # adding results via their genre
    data_album = load_data_products()

    # with px_range only
    io = 0

    # Get all the products based on the genre given.
    for album_name, u in data_album.items():
        if (str(gnr).lower() == str(u["genre"]).lower()) or gnr is None:
            io += 1

            # filtering items based on price range
            if check_price_range(u["price"]):
                stored_data[album_name] = u

                if album_name in c:
                    stored_data[album_name]["in_cart"] = True
                else:
                    stored_data[album_name]["in_cart"] = False

    # pass the result back in tuple
    if px_range is not None:
        return stored_data, io

    return stored_data


def px_range_post_inversion(r):
    """Invert a name from snake case and return a non-technical naming convention."""
    if r == "below_15":
        return "Below $15"
    elif r == "15_to_30":
        return "$15 to $30"
    if r == "30_to_50":
        return "$30 to $50"
    if r == "50_to_100":
        return "$50 to $100"
    if r == "above_100":
        return "Above $100"
    else:
        return None


def add_to_cart_action(mdl, product, qty):
    """Add a specific items into a cart, via dictionary, if the conditions are met."""
    cart = get_entry("cart")
    unit_product = mdl[product]

    if unit_product["stock"] > 0:  # validate their stock

        # Check whether the item is in cart already
        if product not in cart:
            cart[product] = {
                "artist": unit_product["artist"],
                "id": unit_product["id"],
                "label": unit_product["label"],
                "genre": unit_product["genre"],
                "image": unit_product["image"],
                "price": unit_product["price"],
                "quantity": qty,
                "release_date": unit_product["release_date"],
            }

            save_entries(cart=cart)  # save changes on cart
            flash(f"({qty}) {product} added to cart.")

            # key variables by item to show; critical for side panel access
            flash("%.show_panel_1;")
            flash({
                product: {
                    "id": unit_product["id"],
                    "artist": unit_product["artist"],
                    "image": unit_product["image"],
                    "price": unit_product["price"],
                    "quantity": qty,
                }
            })
        else:
            flash(f"{product} was already in your cart.")

    else:
        # out of stock message
        flash(f"Sorry, but {product} ran out of stock.")


def pole_end_redirect(pole_end: str, alb: dict, ctd_id):
    """Pole End is a method for same route redirection.

    A pole_end is just another way whether to
    redirect the user back into the same page they
    are after the action.

    The pattern is only applicable for item_genre page;
    these pattern must correspond to the pole_end
    as string.

    actions:
        (1) First condition identifies whether
            to redirect user back to item genre.
        (1) It fetches the genre and price range
            if have one, at index [2]).
        (1) Now prompt the user back to the item
            genre ("all" or specific genre). For
            specific genre, it verified whether
            it exists.
        (~) The rest of the pole_end is
            recognised as route name.

    Returns:
    |   redirect routes

    """
    def validate_price_range():
        # validate if price_range is included and apply
        try:
            return f"{genre_condition[2]}".replace("-", "_")
        except:
            return False

    global genre_condition

    redirect_to_grid_pattern = re.compile(r'^\d{1}[%][a-z-]+', re.IGNORECASE)
    genre_pattern = re.compile(r'[a-z0-9-]+', re.IGNORECASE)

    redirect_to_grid_condition = redirect_to_grid_pattern.findall(pole_end)
    genre_condition = genre_pattern.findall(pole_end)

    # redirect users back based on where they currently at
    if type(pole_end) == str and pole_end[0] == "1":
        if redirect_to_grid_condition:
            gn = str(genre_condition[1]).lower()  # genre
            has_px_range = validate_price_range()

            try:
                # genre is any, selecting all items via "all"
                if gn == "all":
                    if has_px_range:
                        return redirect(url_for("category_price_filter",
                                                genre="all",
                                                price_range=has_px_range))

                    return redirect(url_for("category_all"))

                # verify if there is an existing genre
                for y in alb.items():
                    if gn == str(y[1]["genre"]).lower():
                        if has_px_range:
                            return redirect(url_for("category_price_filter",
                                                    genre=gn,
                                                    price_range=has_px_range))

                        return redirect(url_for("category", genre=gn))

            except Exception as failed_pole_genre_execution:
                logger(False, f"POLE EXECUTION FAILED: {failed_pole_genre_execution}", "closed_log")

    elif pole_end == "wishlist":
        return redirect(url_for("wishlist"))

    elif pole_end == "index":
        return redirect(url_for("index"))

    # to a current product info page
    return redirect(url_for("product_information", id=ctd_id))


def panel_access_from_flash():
    """Get the access key to build side panel template across HTML page.

    Prerequisites:
    |   for <fragment> requires "%.show_panel_<int>" to be present.
    |   for <by_pair>, it requires the value as a dict
        to be adjacent below the fragment and to be present.

    actions:
    |   executes code inside for-block loop if contains flashed message.
    |   selects the flash message and looks for the pattern:
        >   %.show_panel
    |   prepare the acccess key if <by_pair> is dictionary

    returns:
        side panel access key //
        -- or --
        None (no flash message or prerequisites are not met, or error happens)

    """
    def when_collection(wn, aa):
        # 1 = Item Added to Cart
        if wn == 1:
            return aa["quantity"], aa["price"] * aa["quantity"], aa["image"]

        # 2 = Item Added to Wishlist
        elif wn == 2:
            return 1, aa["price"], aa["image"]

        # 3 = Notice on Stock Changes
        elif wn == 3:
            return 1, 1, None

    flash_syntax = get_flashed_messages()  # as flash message
    formulate_key_access = {
        "show": True,
        "type": "show_specific_items",
        "when": 0,
        "by": {}
    }

    try:
        # regexp compilation
        show_panel_pattern = re.compile(r'%.show_panel', re.IGNORECASE)
        when_pattern = re.compile(r'_\d+', re.IGNORECASE)

        # execute code inside for-block if contains flash message
        for m in range(len(flash_syntax)):
            fragment = show_panel_pattern.findall(str(flash_syntax[m]))

            if fragment:  # look for the pattern '%.show_panel'
                when_var = when_pattern.findall(str(flash_syntax[m]))
                by_pair = flash_syntax[m + 1]  # adjacent message just below the fragment

                # dictionary only
                if type(by_pair) is dict:
                    when_int = int(f"{when_var[0]}".replace("_", ""))
                    formulate_key_access["when"] = when_int

                    # preparing for the side panel key
                    for album_name, a in by_pair.items():
                        qty, price, img = when_collection(when_int, a)
                        formulate_key_access["name"] = album_name
                        formulate_key_access["id"] = 1 if when_int == 3 else a["id"]

                        formulate_key_access["by"][album_name] = {
                            "id": a["id"],
                            "artist": a["artist"],
                            "image": img,
                            "name": album_name,
                            "quantity": qty,
                            "price": price
                        }

                    return formulate_key_access

    except Exception as side_panel_error:
        logger("INITIATE SIDEPANEL ERROR:", side_panel_error)
        return {
            "show": False,
            "type": "show_specific_items"
        }


def check_date(albm: dict, refer: int):
    """Gather an album date from dict and return the date emphasis.

    Parameters:
    |   album values (dict)
    |   reffering value (int) to work in what method

    Returns:
    |   refer = 0 | "released", "pre-released", "featured"
    |   refer = 1 | "released", "pre-released"
    |   invalid | None

    """
    # constants
    day_current = 20
    current = datetime.datetime(2026, 4, day_current)

    # assuming the current day is 20-04-2026
    date_pattern = re.compile(r'(\d{2})-(\d{2})-(\d{4})')

    # "ID" segment pattern
    id_prime_ptrn = re.compile(r'^\d{3}')  # first segment
    id_mid_ptrn = re.compile(r'\d{4}')  # middle segment

    # access album's date
    album_id = albm["id"]
    dz = albm["release_date"]  # date

    # overall pattern declaration
    pdx, pmx, pyx = date_pattern.findall(dz)[0]
    yx, mx, dx = int(pyx), int(pmx), int(pdx)
    album_release_date = datetime.datetime(yx, mx, dx)

    # refer to three sections: released, featured, pre-release
    if refer == 0:
        rlsd, pre_rlsd = 10, 14
        # -rlsd = show item until/before <release> day(s) from/of release

        pre_id_prime = id_prime_ptrn.findall(album_id)
        pre_id_mid = id_mid_ptrn.findall(album_id)

        # Turning string into integers to be calculatable
        id_prime, id_mid = int(pre_id_prime[0]), int(pre_id_mid[0])

        # latest release
        if 0 <= (current - album_release_date).days <= rlsd:
            return "released"

        # pre-released
        elif pre_rlsd >= (album_release_date - current).days > 0:
            return "pre-released"

        # featured: calculated value == remainder
        elif (id_mid // day_current % 10) == (id_prime % 10):
            return "featured"

    # refer to date only; identify either released or pre-released
    if refer == 1:
        if 0 <= (current - album_release_date).days:
            return "released"
        elif (album_release_date - current).days > 0:
            return "pre-released"


def album_date_modules(loaded_album, rfr):
    """Identify all albums via their date, provided with ther referring value.

    Parameters:
    |   albums (dict)
    |   referring value

    referring value, Returns:
    |   (0) Latest Release, Featured, Pre-released (dict)
    |   (1) Released, Pre-released

    """
    # refer to three_sections only
    if rfr == 0:
        ahrd, bhrd, chrd = [{} for _ in range(3)]

        for na, albm_a in loaded_album.items():
            section_cycle = check_date(albm_a, rfr)

            if section_cycle == "released":
                ahrd[na] = albm_a
            elif section_cycle == "featured":
                bhrd[na] = albm_a
            elif section_cycle == "pre-released":
                chrd[na] = albm_a

        return ahrd, bhrd, chrd

    # refer to date only
    if rfr == 1:
        rlrd, prrd = [{} for _ in range(2)]

        for nb, albm_b in loaded_album.items():
            date_cycle = check_date(albm_b, rfr)

            if date_cycle == "released":
                rlrd[nb] = albm_b
            elif date_cycle == "pre-released":
                prrd[nb] = albm_b

        return rlrd, prrd

    else:
        logger("INVALID REFFERING VALUE", f"({rfr}) No valid reffering value to execute date modules.")
        raise ValueError(f"Inappropriate referring value.\n\n(received {rfr}) Expected: \n0 = three phrase selector\n1 = two phrase selector")


# ROUTES <------------------->

# ===== HOME PAGE
@app.route("/")
def index():
    load_albums = load_data_products()
    cart = verify_existing_product(load_albums, get_entry("cart"), "cart")
    key = panel_access_from_flash()

    try:
        ar, br, cr = album_date_modules(load_albums, 0)

    except Exception as date_module_error:
        logger("DATE MODULE ERROR", date_module_error)
        ar, br, cr = [{"error": date_module_error} for _ in range(3)]

    # three sections
    segment_modules = {
        "latest_release": ar,
        "featured": br,
        "pre-order": cr
    }

    return render_template("index.html", albums=load_albums,
                           segment_modules=segment_modules,
                           cart=cart, key_param=key)


# ===== MUSIC ALBUM PRODUCT INFORMATION
@app.route("/category/item/<id>")
def product_information(id):
    albums = load_data_products()
    pack_data = None

    # Check whether the variable "id" exists; <mv> = item.
    for name, mv in albums.items():
        if id.lower() == mv["id"].lower():
            album_name = name
            album_cycle = check_date(mv, 1)
            pack_data = mv

            break

    else:
        abort(404)

    cart, wishlists = get_entry("cart", "wishlists")
    cart = verify_existing_product(albums, cart, "cart")
    wishlists = verify_existing_product(albums, wishlists, "wishlists")
    key = panel_access_from_flash()

    # Used for alteration to 'input' value if the requested ID is in the cart.
    if album_name in cart:
        current_item = cart[album_name]

    return render_template("product_info.html",
                           product=pack_data, product_name=album_name,
                           in_wishlists=(album_name in wishlists),
                           already_in_cart=(album_name in cart),
                           item_in_hold=(current_item if album_name in cart else False),
                           in_stock=(albums[album_name]["stock"] > 0),
                           album_cycle=album_cycle, key_param=key)


# Add to Cart Route
@app.route("/add_to_cart/<catalogue_id>/<string:product_name>/<string:input_selector>/<pole_end>", methods=["POST"])
def add_to_cart(catalogue_id, product_name, input_selector, pole_end):
    """Add a specific items to a cart.

    actions:
    |   It validates the type of value quantity, then the boundary limits.
    |   It checks for the existing catalogue ID exists.
    |   Then, proceed to the action.

    """
    albums = load_data_products()

    try:
        # when input is not applicable, default is 1 /*/ validate whether the user have entered a number
        quantity = 1 if input_selector == "-1" else int(request.form[input_selector])
        stock = albums[product_name]["stock"]
        limit = 5 if 5 < stock else stock

        if 0 < quantity <= limit:

            # 1. Check whether the requested catalogue ID exists.
            for _, mvt in albums.items():
                if catalogue_id == mvt["id"]:
                    # 2. Initiate an add to cart action.
                    add_to_cart_action(albums, product_name, quantity)
                    break

            else:
                flash(f"Item '{catalogue_id}' could not be found. Double check that the catalogue ID exists.")

        else:            
            if quantity > 0:
                if limit == 1:
                    flash(f"Our stock for {product_name} is not enough for order placement; it has {limit} left.")
                else:
                    flash(f"Please enter a quantity between 1 to {limit}.")
            else:
                flash(f"Please enter a quantity equal to 1.")

    except ValueError:
        flash("We could not add that item. Please enter a number in integer only.")

    except Exception as add_to_cart_error:
        logger("ADD TO CART ERROR", add_to_cart_error)
        flash("Sorry, but there was a problem when we attempted to add that item to your cart. Try again later.")

    # return to page
    return pole_end_redirect(pole_end, albums, catalogue_id)


@app.route("/remove_item/<string:album_name>", methods=["POST"])
def remove_item(album_name):
    cart = get_entry("cart")

    # Remove a selected item out from the cart
    if album_name in cart:
        remove_status = remove_specific_key(cart=album_name)

        if remove_status:
            flash(f"Removed all '{album_name}' in your cart")

    else:
        flash(f"'{album_name}' was not found in your cart or was already removed.")

    return redirect(url_for("cart"))


@app.route("/remove_all_items", methods=["POST"])
def remove_all_items():
    # remove all items in the cart
    try:
        remove_key("cart")
        flash("Removed all items in your cart.")

    except Exception as remove_all_error:
        logger("REMOVE ALL ITEMS ERROR", remove_all_error)
        flash("Something went wrong while removing all the items in your cart. Try again later.")

    return redirect(url_for("cart"))


@app.route("/apply_changes", defaults={"redirection": "cart", "target": "all"}, methods=["POST"])
@app.route("/apply_changes/<redirection>/<target>", methods=["POST"])
def apply_changes(redirection, target):
    album_products = load_data_products()
    cart = get_entry("cart")

    for n, items in cart.items():
        # target name constitute to the product name in order to proceed to change process
        if items.get("is_unavailable") or (target != "all" and target != items["id"]):
            continue

        # value change process
        try:
            # value validation
            stock = album_products[n]["stock"]
            max_quantity = stock if stock < 5 else 5
            qty = int(request.form[f"i-invn-{items['id']}"])

            if qty == cart[n]["quantity"]:  # no changes to value
                pass

            elif 0 < qty <= max_quantity and items['quantity'] != qty:
                cart[n]["quantity"] = qty

            elif qty > max_quantity:
                flash(f"({n}) That value should not exceed more than {max_quantity} maximum.")

            elif 0 >= qty:
                flash(f"({n}) That value should not be less than 1 minimum.")

        except ValueError:
            logger(False, f"NON-INTEGER VALUE: ({n})", "closed_log")
            flash(f"({n}) Please enter a number in integers only to adjust that quantity.")

        except Exception as e:
            logger(False, f"({n}) Failed to fetch a value: {e}", "closed_log")
            flash(f"({n}) Can't change the quantity due to an error.")

    save_entries(cart=cart)

    if redirection == "product_information":
        return redirect(url_for("product_information", id=target))

    return redirect(url_for("cart"))


@app.route("/accept_changes", methods=["POST"])
def accept_changes():
    get_albums = load_data_products()
    cart = get_entry("cart")

    try:
        # change the current quantity to (max) stock limit if qty > stock limit
        for album_name, v in cart.items():
            if v["quantity"] > get_albums[album_name]["stock"]:
                cart[album_name]["quantity"] = get_albums[album_name]["stock"]

        save_entries(cart=cart)

        flash("Quantity successfully changed.")

    except:
        logger("ACCEPT CHANGE ERROR", "Failed to make changes to the products.")

    return redirect(url_for("cart"))


@app.route("/toggle_wishlist/<catalogue_id>/<string:album_name>", defaults={"pole_end": None, "force_removal": False}, methods=["POST"])
@app.route("/toggle_wishlist/<catalogue_id>/<string:album_name>/<string:pole_end>/<force_removal>", methods=["POST"])
def toggle_wishlist(catalogue_id, album_name, pole_end, force_removal):
    """Toggle (add or remove) items in the wishlist.

    This is supported only one item per action.

    """
    albums = load_data_products()
    wishlists = get_entry("wishlists")

    # 1. Check whether the requested catalogue ID exists.
    for _, mvt in albums.items():
        if catalogue_id.lower() == mvt["id"].lower():
            break

    else:
        flash(f"Item '{catalogue_id}' could not be found. Double check that the catalogue ID exists.")
        return redirect(url_for("product_information", id=catalogue_id))


    try:
        # 2. Toggle item; either add or remove
        if album_name not in wishlists and not force_removal:
            wishlists[album_name] = {
                "artist": albums[album_name]["artist"],
                "id": albums[album_name]["id"],
                "label": albums[album_name]["label"],
                "genre": albums[album_name]["genre"],
                "image": albums[album_name]["image"],
                "price": albums[album_name]["price"]
            }

            save_entries(wishlists=wishlists)
            flash(f"{album_name} added to your wishlist")

            flash("%.show_panel_2;")
            flash({
                album_name: {
                    "id": albums[album_name]["id"],
                    "artist": albums[album_name]["artist"],
                    "image": albums[album_name]["image"],
                    "price": albums[album_name]["price"],
                }
            })  # key variables by item to show; critical for side panel access

        else:
            wishlist_remove_status = remove_specific_key(wishlists=album_name)

            if wishlist_remove_status:
                flash(f"{album_name} removed from your wishlist")

    except:
        flash("Sorry, but there was a problem when we tried to adjust your wishlist. Try again later.")

    # pole end
    if pole_end == "wishlist":
        return redirect(url_for("wishlist"))

    return redirect(url_for("product_information", id=catalogue_id))


# ===== ITEM GENRE (display all items)
@app.route("/category/item")
def category_all():
    get_albums = load_data_products()
    cart = verify_existing_product(get_albums, get_entry("cart"), "cart")
    key = panel_access_from_flash()
    result = item_display_by_genre()  # get the result via genre
    _, pr = album_date_modules(get_albums, 1)

    return render_template("item_genre.html", genre="all",
                           imported_data=result, cart=cart,
                           key_param=key, pr=pr)


# ===== ITEM GENRE (specific genre)
@app.route("/category/item-<string:genre>")
def category(genre):
    result = item_display_by_genre(genre)  # get the result via genre

    if result == {}:  # empty and specific genre is not found
        abort(404)

    get_albums = load_data_products()
    cart = verify_existing_product(get_albums, get_entry("cart"), "cart")
    key = panel_access_from_flash()
    _, pr = album_date_modules(get_albums, 1)

    return render_template("item_genre.html", genre=genre,
                           imported_data=result, cart=cart,
                           key_param=key, pr=pr)


# ===== ITEM GENRE (filtered price range)
@app.route("/category/item-<string:genre>/<price_range>")
def category_price_filter(genre, price_range):
    kebab_case_pxrange = f"{price_range}".replace("_", "-")  # used for add to cart action to redirect back here
    text_value = px_range_post_inversion(price_range)
    text_value = text_value.lower() if text_value is not None else text_value

    # define gni to the result via genre and price
    if genre == "all":
        gni = None
    else:
        gni = genre

    result, gio = item_display_by_genre(gni, price_range)

    # genre is not found or price range is not exists
    if gio <= 0 or text_value is None:
        abort(404)

    get_albums = load_data_products()
    cart = verify_existing_product(get_albums, get_entry("cart"), "cart")
    key = panel_access_from_flash()
    _, pr = album_date_modules(get_albums, 1)

    return render_template("item_genre.html", genre=genre,
                           text_value=text_value, pxrange=kebab_case_pxrange,
                           imported_data=result, cart=cart,
                           key_param=key, pr=pr)


# get the filter price as string version
@app.route("/filter_price/<string:genre>", methods=["POST"])
def filter_price(genre):
    try:
        selected_range = request.form["price-range"]

        # in snake case, naming convention
        srg = f"{selected_range.replace(' ', '_').replace('$', '')}".lower()

    except KeyError:
        flash("Select a range to filter out products based on price.")

        if genre == "all":
            return redirect(url_for("category_all"))
        else:
            return redirect(url_for("category", genre=genre))

    # redirect with filtering item in price
    return redirect(url_for("category_price_filter",
                            genre=genre, price_range=srg))


# ===== INVOICE PAGE
@app.route("/invoice-<int:inv_number>")
def invoice_selection(inv_number):
    # sqlite3 \
    try:
        with sqlite3.connect("order_history.db") as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM orders WHERE id = {inv_number}")
            rows = cursor.fetchall()[0]  # fetching for one row only

            albums = load_data_products()
            _, pr = album_date_modules(albums, 1)
            key = panel_access_from_flash()

            second_row = json.loads(rows[2])
            load_items = json.loads(rows[3])
            items_on_hold = {} if not rows[9] else json.loads(rows[9])
            items = {}
            s = 0  # used for number listing

            # index registration
            for album_name, m in load_items.items():
                s += 1
                items[album_name] = {
                    "no": s,
                    "artist": m["artist"],
                    "id": m["id"],
                    "label": m["label"],
                    "genre": m["genre"],
                    "price": m["price"],
                    "quantity": m["quantity"],
                }

            # overall result
            fetched_data = {
                "id": rows[0],
                "date": rows[1],
                "customer": {
                    "name": second_row["name"],
                    "email": second_row["email"],
                    "physical_address": second_row["physical_address"],
                    "town": second_row["town"],
                    "postal_code": second_row["postal_code"],
                },
                "items": items,
                "subtotal": rows[4],
                "gst": rows[5],
                "ship_fee": rows[6],
                "discount": rows[7],
                "total_charges": rows[8],
                "items_on_hold": items_on_hold,
            }

    except IndexError:
        abort(404)  # not found

    except Exception as get_invoice_error:
        logger("GET INVOICE ERROR:", get_invoice_error)
        fetched_data = {
            "error": str(get_invoice_error)
        }

    return render_template("invoice.html", albums=albums,
                           data=fetched_data, key_param=key,
                           pr=pr)


# ===== ORDER HISTORY PAGE
@app.route("/order_history")
def order_history():
    def check_error_strikes(orders):
        # log message if encountered full error strikes

        error_strikes = sum(1 if "error" in pr.keys() else 0 for pr in orders)
        if error_strikes == len(order_history_results) and len(order_history_results) != 0:
            logger("ORDER HISTORY ERROR", "Strike reached fully due to persistent errors; order history table can't be displayed.")

    with sqlite3.connect("order_history.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM orders")

        # fetched data
        o_rows = cursor.fetchall()
        order_history_results = []

        # each ordered place from list on o_rows
        for orders in o_rows:
            id = orders[0]

            try:
                order_history_results.append({
                    "order_id": id,
                    "date": orders[1],
                    "customer": json.loads(orders[2]),
                    "items": json.loads(orders[3]),
                    "subtotal": orders[4],
                    "gst": orders[5],
                    "ship_fee": orders[6],
                    "discount": orders[7],
                    "total_charges": orders[8],
                })

            except Exception as path_error:
                logger(False, f"({id}) {path_error} [received from order history route]", "closed_log")
                order_history_results.append({"error": str(path_error)})

        check_error_strikes(order_history_results)

    return render_template("order_history.html", orders=order_history_results)


# Order History: Deletion of a Selected Invoice Number
@app.route("/delete_invoice/<int:order_id>", methods=["POST"])
def delete_invoice(order_id):
    with sqlite3.connect("order_history.db") as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))

            conn.commit()

            flash(f"Invoice #{order_id} deleted.")

        except sqlite3.Error as delete_invoice_error:
            conn.rollback()

            logger("DELETE INVOICE ERROR", delete_invoice_error)
            flash(f"Invoice #{order_id} deletion has been halted to due to error.")

    return redirect(url_for("order_history"))


# ===== CART PAGE
@app.route("/cart")
def cart():
    albums = load_data_products()

    # Get cart via session.get
    cart = verify_existing_product(albums, get_entry("cart"), "cart")
    _, pr = album_date_modules(albums, 1)
    coupon_validity()

    # Get price calculation
    __n, subtotal, gst, __n2, discount, __n3 = calculate_total(cart)

    return render_template("cart.html", cart=cart, albums=albums,
                           subtotal=subtotal, gst=gst, discount=discount,
                           pre_released=pr)


# ===== WISHLIST PAGE
@app.route("/wishlist")
def wishlist():
    albums = load_data_products()
    key = panel_access_from_flash()
    cart, wishlists = get_entry("cart", "wishlists")
    _, pr = album_date_modules(albums, 1)

    cart = verify_existing_product(albums, cart, "cart")
    wishlists = verify_existing_product(albums, wishlists, "wishlists")

    return render_template("wishlist.html", cart=cart,
                           wishlists=wishlists, albums=albums,
                           key_param=key, pre_released=pr)


# Applying a Coupon
@app.route("/apply_coupons", methods=["POST"])
def apply_coupons():
    try:
        input_coupon = request.form["coupon"].upper()  # get user's input
        get_data_coupon = load_data_coupons()  # get the data of the coupons
        sets_used_coupons = get_entry("used_coupons")

        # blank input
        if input_coupon == "":
            flash("Please enter a coupon name")

        # if coupon exists
        elif input_coupon in get_data_coupon:
            if input_coupon not in sets_used_coupons:  # not already used
                save_entries(coupon={
                    "name": input_coupon,
                    "discount": get_data_coupon[input_coupon]["discount"]
                })  # applying coupon into session

                flash("Coupon applied")

            else:
                flash("Oops! You've already used that coupon.")

        else:
            flash(f"Coupon '{input_coupon}' does not exist")

    except Exception as apply_coupon_error:
        logger("APPLY COUPON ERROR:", apply_coupon_error)
        flash("An error has occurred while trying to apply the coupon. Try again later.")

    return redirect(url_for("cart"))


# Removing a Coupon
@app.route("/remove_coupon", methods=["POST"])
def remove_coupon():
    is_removed = remove_coupon_action()
    if is_removed:
        flash(f"Removed a coupon: {is_removed["removed_cpn_name"]}. You can still enter it unless or until you have used it.")

    return redirect(url_for("cart"))


# ===== CHECKOUT PAGE
@app.route("/checkout")
def checkout():
    cart, billing_info = get_entry("cart", "billing_info")
    coupon_validity()

    total, subtotal, gst, ship_fee, discount, total_with_discount = calculate_total(cart)

    if not cart:
        flash("You don't have items in your cart yet; start shopping for your favourite music album.")
        return redirect(url_for("cart"))

    return render_template("checkout.html",
                           total=total, subtotal=subtotal,
                           gst=gst, ship_fee=ship_fee,
                           cart=cart, discount=discount,
                           total_with_discount=total_with_discount,
                           saved_billing_info=billing_info)


# ===== ORDER REVIEW PAGE
@app.route("/continue_to_review")
def continue_to_review():
    cart, billing_info = get_entry("cart", "billing_info")
    coupon_validity()

    total, subtotal, gst, ship_fee, discount, total_with_discount = calculate_total(cart)

    # validation (in billing info, check if some detail(s) are missing, except postal code)
    if (not cart or not billing_info) or (None in billing_info.values()):
        if (cart and not billing_info) or None in billing_info.values():
            flash("You are missing with important thing. Enter your billing details so we can track your order.")

        return redirect(url_for("checkout"))

    return render_template("checkout_review.html",
                           total=total, subtotal=subtotal,
                           gst=gst, ship_fee=ship_fee,
                           cart=cart, discount=discount,
                           total_with_discount=total_with_discount,
                           saved_billing_info=billing_info)


@app.route("/continue_to_review/get", methods=["POST"])
def get_details():
    billing_info = get_entry("billing_info")
    billing_info = {
        "first_name": request.form["first-name"],
        "surname": request.form["surname"],
        "email": request.form["email"],
        "physical_address": request.form["physical-addr"],
        "town": request.form["suburb"],
        "postal_code": request.form["postal-code"]
    }

    save_entries(billing_info=billing_info)

    return redirect(url_for("continue_to_review"))


# Placing Order
@app.route("/place_order", methods=["POST"])
def place_order():
    cart, coupon, billing_info = get_entry("cart", "coupon", "billing_info")

    # check if the cart or billing info is not empty
    if (not cart or not billing_info) or (None in billing_info.values()):
        time.sleep(0.9)

        # missing details
        if (cart and not billing_info) or None in billing_info.values():
            flash("You are missing with important thing. Enter your billing details so we can track your order.")

        return redirect(url_for("checkout"))

    time.sleep(2.4)  # time delay

    # define the details and order info via order placement
    customer_name = f"{billing_info["first_name"]} {billing_info["surname"]}"
    customer = {
        "name": customer_name,
        "email": billing_info["email"],
        "physical_address": billing_info["physical_address"],
        "town": billing_info["town"],
        "postal_code": billing_info["postal_code"],
    }

    total, subtotal, gst, ship_fee, discount, total_with_discount = calculate_total(cart)
    main_total = total if total == total_with_discount else total_with_discount
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    time_clock = datetime.datetime.now().strftime("%H.%M.%S")
    invoice_date = f"{date} {time_clock}"
    invoice_filename = f"INV_{customer_name.replace(" ", "_")}_{date}.txt"

    # Save order history to SQLite Database
    with sqlite3.connect("order_history.db") as conn:
        try:
            reserved_assets = update_stock(cart)
            on_hold_items = streamlined_demand(reserved_assets)

            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders
                (date, customer, items, subtotal,
                gst, ship_fee, discount, total_charges,
                items_on_hold)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice_date, json.dumps(customer),
                  json.dumps(cart), subtotal, gst,
                  ship_fee, discount, main_total,
                  json.dumps(on_hold_items)))
            conn.commit()

        except Exception as place_order_error:
            conn.rollback()  # reverts the changes

            logger("PLACE ORDER ERROR", place_order_error)
            flash(f"An error has occurred while placing your order. DEBUG TRACE: {place_order_error}")

            return redirect(url_for("index"))
        
    # write an invoice in .txt version
    with open(invoice_filename, "w") as f:
        try:
            f.write("<-----> The Music Shop <----->\n")

            f.write(f"Invoice Number: {invoice_date}\n")
            f.write(f"Customer Name: {customer_name}\n")
            f.write(f"Date: {invoice_date}\n\n")

            f.write(f"Items:\n\n")

            for album_name, m in cart.items():
                f.write(f"-- {album_name}: {m["quantity"]} x ${m["price"]} = ${m["quantity"] * m["price"]:.2f}\n")

            f.write(f"\nSubtotal: ${subtotal:.2f}\n") if subtotal else None
            f.write(f"GST: ${gst:.2f}\n") if gst else None
            f.write(f"Delivery Fee: ${ship_fee:.2f}\n") if ship_fee else None
            f.write(f"Discount: ${discount:.2f}\n\n") if discount else None

            f.write(f"Total: ${main_total:.2f}\n")

        except Exception as write_invoice_txt_error:
            logger("WRITE INVOICE ERROR", write_invoice_txt_error)
            flash("Failed to write an invoice text:", write_invoice_txt_error)

    # take out all items in cart, and coupon
    spike_used_coupon(coupon)
    remove_key("cart", "coupon")
    flash("Order Completed")

    # finally, redirect user to invoice page
    try:
        with sqlite3.connect("order_history.db") as conn:
            # fetch for id only
            cursor.execute(f"SELECT * FROM orders WHERE date = '{invoice_date}'")
            lid = cursor.fetchall()[0]  # fetching for one row only
            redirect_id = lid[0]

        return redirect(url_for("invoice_selection", inv_number=int(redirect_id)))

    except Exception as redirect_error:
        logger(False, f"Failed to redirect to invoice number:, {redirect_error}", "closed_log")

    return redirect(url_for("index"))


# ===== SIGNUP/LOGIN PAGE
@app.route("/accounts/<measure>", defaults={"subject": None})
@app.route("/accounts/<measure>/<subject>")
def signup_login(measure, subject):
    if measure != "signup" and measure != "login":
        abort(404)  # not found

    # verify if the user was logged on
    if session.get("session_key", {}).get("accessed"):
        return redirect(url_for("my_account"))

    return render_template("account_access.html", msr=measure, sbj=subject)


# signup process
@app.route("/signup", defaults={"get_subject": None}, methods=["POST"])
@app.route("/signup/<get_subject>", methods=["POST"])
def signup(get_subject):
    # define a new user
    fname = request.form["new-fname"].strip().title()
    lname = request.form["new-lname"].strip().title()
    email = request.form["new-email"]
    password = request.form["new-password"]
    confirm_password = request.form["new-confirm-password"]

    name = f"{fname} {lname}"  # full name
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    billing_info = {
        "first_name": fname,
        "surname": lname,
        "email": email,
        "physical_address": None,
        "town": None,
        "postal_code": None
    }

    # Complete Registration to Database
    try:
        # confirming a password
        if password == confirm_password:
            cart = session.get("cart", {})
            wishlists = session.get("wishlists", {})

            # Connect to SQLite3: accounts
            with sqlite3.connect("accounts.db") as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO accounts
                    (date, name, email, password, items,
                    wishlists, billing_info, applied_coupon,
                    used_coupons)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (date, name, email,
                      password, json.dumps(cart),
                      json.dumps(wishlists), json.dumps(billing_info),
                      "{}", "{}"))

                conn.commit()

            signin_session(email, password)
            flash(f"Welcome, {name}!")

        else:
            flash("Your password does not matched the one you are trying to confirm. Verify that the password is the same as the one you created.")
            return redirect(url_for("signup_login", measure='signup',
                                    subject=get_subject))

    except Exception as signup_error:
        logger("SIGNUP ERROR", signup_error)
        flash(f"Something went wrong while we are trying to sign you up: {signup_error}")

        return redirect(url_for("index"))

    # return to checkout via "get_subject"
    if get_subject == "for_awaiting_checkout":
        return redirect(url_for("checkout"))

    return redirect(url_for("index"))


# login process
@app.route("/login", defaults={"get_subject": None}, methods=["POST"])
@app.route("/login/<get_subject>", methods=["POST"])
def login(get_subject):
    email = request.form["lg-email"]
    password = request.form["lg-password"]

    try:
        signin_session(email, password, 1)

    except (NameError, ValueError) as err:
        flash(f"{err}")
        return redirect(url_for("signup_login", measure='login',
                                subject=get_subject))

    except Exception as login_error:
        logger("LOGIN ERROR", login_error)
        flash("Oops! Something went wrong. Please try again later.")

        return redirect(url_for("signup_login", measure='login',
                                subject=get_subject))

    # return to checkout via "get_subject"
    if get_subject == "for_awaiting_checkout":
        return redirect(url_for("checkout"))

    return redirect(url_for("index"))


# ===== MY ACCOUNT PAGE
@app.route("/accounts/my_account")
def my_account():
    has_session_key = session.get("session_key", {})

    # verify if the user was logged on
    if has_session_key.get("accessed"):
        return render_template("account_access.html", msr=None, sbj=None)

    return redirect(url_for("signup_login", measure='login'))


# logout
@app.route("/logout", methods=["POST"])
def logout():
    # revoke session account
    session.pop("session_key", None)
    session.modified = True

    return redirect(url_for("signup_login", measure='login'))


# ===== ATTRIBUTION PAGE
@app.route("/attribution")
def attribution():
    try:
        with open("data/attribution.json") as attr:
            loaded_attributon = json.load(attr)

    except Exception as load_attribution_error:
        logger("LOAD ATTRIBUTION ERROR", load_attribution_error)
        loaded_attributon = {}

    return render_template("attribution.html", attr=loaded_attributon)


if __name__ == "__main__":
    initialise_database()

    app.run(debug=True)
