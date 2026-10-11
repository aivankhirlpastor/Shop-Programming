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
                    total_charges REAL
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

def update_stock(item: dict):
    reserved = {} # on partial fulfillment or backorder

    with open("data/products.json", "r") as product:
        fetched_album_data = json.load(product)

    for album_name, i in item.items():
        if album_name in fetched_album_data:

            album_module_cycle = check_date(album_name, i, 1)

            # no quantity changes on pre-released items
            if not album_module_cycle == "pre-released":
                fetched_stock = fetched_album_data[album_name]["stock"]
                fetched_stock -= i["quantity"] # modify the stock
            else:
                # pre-release items reserved
                reserved[album_name] = {
                    "id": i["id"],
                    "artist": i["artist"],
                    "name": album_name,
                    "call": "before_released",
                    "cause_of_demand": "pre_order",
                    "demand_tracking": f"limit: n/a | demand: {i["quantity"]}",
                    "quantity_demand": i["quantity"]
                }

                continue

            # prompt when stock reached 0 or beyond
            if fetched_stock < 0:
                # out of stock measurement
                if fetched_stock <= -1 * i["quantity"]:
                    demand_cause = "out_of_stock"

                # quantity demand exceeded the stock inventory
                else:
                    demand_cause = "exceeded"

                fetched_stock = 0
                reserved[album_name] = {
                    "id": i["id"],
                    "artist": i["artist"],
                    "name": album_name,
                    "call": "suspended",
                    "cause_of_demand": demand_cause,
                    "demand_tracking": f"limit: {fetched_album_data[album_name]["stock"]} | demand: {i["quantity"]}",
                    "quantity_demand": i["quantity"]
                }

            # change the stock inventory
            fetched_album_data[album_name]["stock"] = fetched_stock

    with open("data/products.json", "w") as product:
        json.dump(fetched_album_data, product, indent = 4)

    return reserved

# verify if the product in cart/wishlist is exists;
# used for error prevention to missing music album and mismatched catalogue id
def verify_existing_product(loaded_albums: dict, val: dict, target: str, allow_change = True):
    new_value = {}
    strike = 0

    for album_name, v in val.items():
        # if the name within 'val' is not found
        if not loaded_albums.get(album_name):
            strike += 1

            for n, uv in loaded_albums.items():
                if uv["id"] == v["id"]:
                    new_value[n] = v # change the name
                    break
            else:
                new_value[album_name] = v
                new_value[album_name]["is_unavailable"] = True

        # name in cart/wishlist is exist, but the id is mismatched
        elif not v["id"] == loaded_albums[album_name]["id"]:
            new_value[album_name] = v
            new_value[album_name]["id"] = loaded_albums[album_name]["id"]
            strike += 1

        else:
            new_value[album_name] = v

            if "is_unavailable" in v:
                new_value[album_name].pop("is_unavailable")
    
            # e.g. 'dict object' has no attribute 'The Key To Withstand' (over 'The Key To Withtand')

    if strike > 0 and allow_change:
        if target == "cart":
            save_entries(cart = new_value)
        elif target == "wishlists":
            save_entries(wishlists = new_value)

        return new_value

    return val

# variant words or terms; both severely returns in <term, term for key session>
def discriminate(ry: str):
    if ry == "cart":
        return "items", "cart"
    elif ry == "coupon":
        return ["applied_coupon" for _ in range(2)]

    return [ry for _ in range(2)]

# syntax building for database
def set_syntax_building(argument: dict|list|tuple, positional_value: list|tuple = ()):
    def initialise_build(params: dict) -> dict:
        if not type(params) is dict:
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
                if not tr == "wishlists" or not tr == "billing_info":
                    session_key[term_key_session] = params[tr]

        # finalising prompt
        return set_clause_structure, set_clause_value, session_key

    storer = {}

    # *args
    if type(argument) is tuple or type(argument) is list:
        # verify if both argument and positional values were the same amount of items
        if not len(argument) == len(positional_value):
            raise ValueError(f"The amount of value it has, as a list for positional value, must have the same value as the amount of key argument has: {len(argument)} | {len(positional_value)}")
        
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

# changing database of a currently logged on account (saving)
def make_change_to_database(syntax_structure: list, syntax_val: list, key_session):
    # updating database table
    session_key = session.get("session_key", {})

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
        
# Strict Searching in registered accounts:
# requires the variable 'name' to be listed
# under existing columns from database accounts.

# use 'get_entry' function when dealing with two sides
def get_entry(*args):
    result = []
    has_session_key = session.get("session_key", {})

    try:
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

    return result[0] if len(args) == 1 else result # fetched keywords

# saving their entries via session or database |  multiple kws, required argument: (key = value)
def save_entries(**kwargs):
    has_session_key = session.get("session_key", {})

    try:
        # guest
        if not has_session_key:
            for tg, value in kwargs.items():
                session[tg] = value

            session.modified = True # finalising by saving the session
            return {
                "is_saved": "session",
                "status": 1
            }

        # session with user being logged on
        else:
            syntaxes, stx_value, sess_key = set_syntax_building(kwargs)
            return make_change_to_database(syntaxes, stx_value, sess_key) # updating database table

    except Exception as save_error:
        logger("SAVE ERROR", save_error)
        flash(f"An error occurred while attempting to save configuration.")

# removing specific key on dictionary: (name of session/column = key)
def remove_specific_key(**kwargs):
    has_session_key = session.get("session_key", {})

    try:
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
            value_to_save = [] # stored after a "del" action

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
                        value_to_save.append(items)
                    elif column == "wishlists":
                        del wishlists[key]
                        value_to_save.append(wishlists)
                    elif column == "billing_info":
                        del billing_info[key]
                        value_to_save.append(billing_info)
                    elif column == "applied_coupon" or column == "coupon":
                        del applied_coupon[key]
                        value_to_save.append(applied_coupon)
                    elif column == "used_coupons":
                        del used_coupons[key]
                        value_to_save.append(used_coupons)

            syntaxes, stx_value, sess_key = set_syntax_building(tuple(kwargs.keys()), value_to_save)
            return make_change_to_database(syntaxes, stx_value, sess_key)
            
    except Exception as remove_key_error:
        logger("REMOVE SPECIFIC KEY(S) ERROR", remove_key_error)
        flash(f"An error occurred while attempting to remove specific key(s).")

        return None # unsuccessful deletion of specific key

def remove_key(*args):
    has_session_key = session.get("session_key", {})

    try:
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
            syntaxes, stx_value, sess_key = set_syntax_building(args, ({},) * len(args))
            return make_change_to_database(syntaxes, stx_value, sess_key)

    except Exception as delete_error:
        logger("DELETE ERROR", delete_error)
        print(f"An error occurred while attempting to make configuration.")
        return None # unsuccessful pop deletion

# -----------------------------------------------------------------------------------

def signin_session(email, password, msr = 0):
    # getting onto session
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

            # if not matched
            if not password == uid[4]:
                raise ValueError("Password is incorrect")

            # log in method
            if msr == 1:
                # retrieving the column values
                retrieved_coupon = json.loads(uid[8])
                retrieved_used_coupons = json.loads(uid[9])

            # In-Session Key in dict (account accessed)
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

            session["session_key"] = session_key # define the session key
            session.modified = True
        else:
            # empty post_identifier
            raise NameError(f"{email} is not found. Try double checking your email.")

def calculate_total(c):
    # round() and *100/100 rule to alleviate math float inaccuracy
    cart_total = sum((item["price"] * item["quantity"]) * 100 for item in c.values())
    cart_total = cart_total / 100
    gst = round(cart_total * 0.15, 2)
    shipping_fee = 0 # initial

    # Shipping Fee: Determined by subtotal
    if cart_total > 200:
        shipping_fee = 5.3
    elif 200 >= cart_total > 100:
        shipping_fee = 2.7

    # calculate for total
    main_total = cart_total + gst + shipping_fee

    # get discount via session
    discount_value = 0
    tl_w_disc = main_total
    has_coupon_applied = get_entry("coupon")

    if not has_coupon_applied == {}:
        discount_value = has_coupon_applied["discount"]

        # determination by value
        if discount_value > 1: # via regular whole number
            tl_w_disc = main_total - discount_value
        elif discount_value <= 1: # via percentage
            tl_w_disc = main_total - (main_total * discount_value)

        # reached below zero (negative)
        if tl_w_disc < 0:
            tl_w_disc = 0

    return main_total, cart_total, gst, shipping_fee, discount_value, tl_w_disc

def remove_coupon_action():
    try:
        cpn_name = get_entry("coupon")["name"] # get the dict value first, then the coupon name
        removal_status = remove_key("coupon")

        if not removal_status:
            return

    except:
        return False

    return {
        "removed_cpn_name": cpn_name,
    }

def coupon_validity():
    try:
        coupon = get_entry("coupon")
        cpn_name = coupon["name"]
        get_data_coupon = load_data_coupons()

        if cpn_name not in get_data_coupon:
            is_removed = remove_coupon_action()

            flash(f"The coupon you have, {cpn_name}, is no longer valid.")
    except Exception as validate_coupon_error:
        logger(False, f"Failed to validate coupon: {validate_coupon_error}", "closed_log")

# result by their genre (function)
def item_display_by_genre(gnr = None, px_range = None):

    # checking their price range
    def check_price_range(ap):
        # if-else condition via price (px) range
        if px_range == None:
            return True # None to proceed
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
    stored_data = {} # adding results via their genre
    data_album = load_data_products()

    # with px_range only: used to validate whether genre exists
    io = 0

    # Get all the products based on the genre given.
    for album_name, u in data_album.items():
        if (str(gnr).lower() == str(u["genre"]).lower()) or gnr == None:
            io += 1 # add 1 if genre exists by checking item's genre

            if check_price_range(u["price"]):
                # None = display all items
                stored_data[album_name] = u
                stored_data[album_name]["in_cart"] = True if album_name in c else False

    # pass the result back in tuple
    if not px_range == None:
        return stored_data, io

    return stored_data

# Inversion (from snake case of name conventions)
def px_range_post_inversion(r):
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
    cart = get_entry("cart")
    unit_product = mdl[product]

    if unit_product["stock"] > 0: # 3. Validate their stock

        if product not in cart: # Check whether the item is in cart already
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

            save_entries(cart = cart) # save changes on cart

            flash(f"({qty}) {product} added to cart.")
            flash("%.show_panel_1;")
            flash({
                product: {
                    "id": unit_product["id"],
                    "artist": unit_product["artist"],
                    "image": unit_product["image"],
                    "price": unit_product["price"],
                    "quantity": qty,
                }
            }) # key variables by item in order to show; critical for side panel key access

        else:
            flash(f"{product} was already in your cart.")
            
    else:
        # out of stock message
        flash(f"Sorry, but {product} ran out of stock.")

# panel access key function
def panel_access_from_flash():
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

    flash_syntax = get_flashed_messages() # as flash message
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

        # execute for block if contains flash message
        for m in range(len(flash_syntax)):
            if show_panel_pattern.findall(str(flash_syntax[m])): # look for the pattern '%.show_panel'
                when_var = when_pattern.findall(str(flash_syntax[m]))
                by_pair = flash_syntax[m + 1] # adjacent message just below '%.show_panel'

                # dictionary only
                if type(by_pair) is dict:
                    when_int = int(f"{when_var[0]}".replace("_", ""))
                    formulate_key_access["when"] = when_int

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
            else:
                continue

    except Exception as side_panel_error:
        logger("INITIATE SIDEPANEL ERROR:", side_panel_error)
        return None

def check_date(n: str, albm: dict, refer: int):
    # timeline
    DAY_CURRENT = 20
    current = datetime.datetime(2026, 4, DAY_CURRENT)
    date_pattern = re.compile(r'(\d{2})-(\d{2})-(\d{4})')

    # assuming the current day is 20-04-2026

    # "ID" segment pattern
    id_prime_ptrn = re.compile(r'^\d{3}') # first segment
    id_mid_ptrn = re.compile(r'\d{4}') # middle segment

    try:
        # access album's date
        album_id = albm["id"]
        dz = albm["release_date"] # date

        # overall pattern declaration
        pdx, pmx, pyx = date_pattern.findall(dz)[0]
        yx, mx, dx = int(pyx), int(pmx), int(pdx)
        album_release_date = datetime.datetime(yx, mx, dx)

        # refer to three sections: released, featured, pre-release
        if refer == 0:
            RLSD, PRE_RLSD = 10, 14
            # -rlsd = show item until/before <release> day(s) from/of release

            pre_id_prime = id_prime_ptrn.findall(album_id)
            pre_id_mid = id_mid_ptrn.findall(album_id)

            # Turning string into integers to be calculatable
            id_prime, id_mid = int(pre_id_prime[0]), int(pre_id_mid[0])

            # latest release
            if 0 <= (current - album_release_date).days <= RLSD:
                return "released"

            # featured: calculated value == remainder
            elif (id_mid // DAY_CURRENT % 10) == (id_prime % 10):
                return "featured"

            # pre-released
            elif PRE_RLSD >= (album_release_date - current).days > 0:
                return "pre-released"

        # refer to date only; identify either released or pre-released
        if refer == 1:
            if 0 <= (current - album_release_date).days:
                return "released"
            elif (album_release_date - current).days > 0:
                return "pre-released"
    except:
        return

def album_date_modules(loaded_album, rfr):
    # refer to three_sections only
    if rfr == 0:
        ahrd, bhrd, chrd = [{} for _ in range(3)]

        for na, albm_a in loaded_album.items():
            section_cycle = check_date(na, albm_a, rfr)

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
            date_cycle = check_date(nb, albm_b, rfr)

            if date_cycle == "released":
                rlrd[nb] = albm_b
            elif date_cycle == "pre-released":
                prrd[nb] = albm_b

        return rlrd, prrd

    else:
        logger("INVALID REFFERING VALUE", f"({rfr}) No valid reffering value to execute date modules.")
        raise ValueError(f"Inappropriate referring value.\n\n(received {rfr}) Expected: \n0 = three phrase selector\n1 = two phrase selector")

# display error message on terminal output in coloured variants
def logger(types: str = "ERROR", cause = None, sector = "error"):
    if sector == "error":
        print(f"\33[1m\33[91m{types}{f": \33[0m\33[35m{cause}\33[0m" if cause else ""}")

    elif sector == "warning":
        print(f"\33[33m{types}{f": \33[0m\33[3m\33[34m{cause}\33[0m" if cause else ""}")

    elif sector == "closed_log":
        print(f"\33[2m{cause}\33[0m")

# --------------------------------------

# PRE variable declaration \ via research
@app.before_request
def before_load_function():

    # coupon validity
    if session.get("coupon", {}):
        coupon_validity()

# --------------------------------------

# ROUTES <------------------->
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

    segment_modules = {
        "latest_release": ar,
        "featured": br,
        "pre-order": cr
    }

    return render_template("index.html", albums = load_albums,
                           segment_modules = segment_modules,
                           cart = cart, key_param = key)

@app.route("/category/item/<id>")
def product_information(id):
    albums = load_data_products()
    pack_data = None

    # Check whether the variable "id" exists.
    for name, mv in albums.items():
        if id.lower() == mv["id"].lower():
            album_name = name
            album_cycle = check_date(name, mv, 1)
            pack_data = mv
            
            break
    else:
        abort(404)

    cart, wishlists = get_entry("cart", "wishlists")
    cart = verify_existing_product(albums, cart, "cart")
    wishlists = verify_existing_product(albums, wishlists, "wishlists")
    key = panel_access_from_flash()

    # Used for some modification to 'input' value if the requested catalogue ID is in the cart.
    if album_name in cart:
        current_item = cart[album_name]

    # If the condition was passed, move on to prepare for the outputs.
    return render_template("product_info.html",
                           product = pack_data, product_name = album_name,
                           in_wishlists = (album_name in wishlists),
                           already_in_cart = (album_name in cart),
                           item_in_hold = (current_item if album_name in cart else False),
                           in_stock = (albums[album_name]["stock"] > 0),
                           album_cycle = album_cycle, key_param = key)

# Add to Cart Route
@app.route("/add_to_cart/<catalogue_id>/<string:product_name>/<string:input_selector>/<pole_end>", methods = ["POST"])
def add_to_cart(catalogue_id, product_name, input_selector, pole_end):
    albums = load_data_products()

    try:
        # when input is not applicable, default is 1 /*/ validate whether the user have entered a number
        quantity = 1 if input_selector == "-1" else int(request.form[input_selector])

        if 0 < quantity <= 5:
            # 1. Check whether the requested catalogue ID exists.
            for _, mvt in albums.items():
                if catalogue_id == mvt["id"]:
                    # 2. Initiate an add to cart action.
                    add_to_cart_action(albums, product_name, quantity)
                    break
            else:
                flash(f"Item '{catalogue_id}' could not be found. Double check that the catalogue ID exists.")
        else:
            flash(f"Please enter a quantity between 1 to 5.")

    except ValueError:
        flash("We could not add that item. Please enter a number in integer only.")

    except Exception as add_to_cart_error:
        logger("ADD TO CART ERROR", add_to_cart_error)
        flash("Sorry, but there was a problem when we attempted to add that item to your cart. Try again later.")

    # A pole_end is just another way whether to redirect the user back into the same page they are after the action.
    # This is only applicable for item_genre page; these pattern must correspond to the pole_end as string.
    redirect_to_grid_pattern = re.compile(r'^\d{1}[%][a-z-]+', re.IGNORECASE)
    genre_pattern = re.compile(r'[a-z0-9-]+', re.IGNORECASE)

    redirect_condition = redirect_to_grid_pattern.findall(pole_end) # get a number
    genre_condition = genre_pattern.findall(pole_end)

    # redirect users back based on where they currently at (in case to item grid display)
    if type(pole_end) == str and pole_end[0] == "1" and redirect_condition:
        # for genre_condition as list*, [1] is used to take only the genre.
        gn = str(genre_condition[1]).lower()
        
        # from category page, validate if price_range is included; index [2] for price_range
        try:
            has_px_range = f"{genre_condition[2]}".replace("-", "_") # converting kebab case into snake case
        except:
            has_px_range = False

        try:
            if gn == "all":
                if has_px_range:
                    return redirect(url_for("category_price_filter", genre = "all", price_range = has_px_range))

                return redirect(url_for("category_all"))
            
            for y in albums.items():
                # verify if there is an existing genre
                if gn == str(y[1]["genre"]).lower():
                    if has_px_range:
                        return redirect(url_for("category_price_filter", genre = gn, price_range = has_px_range))
                    
                    return redirect(url_for("category", genre = gn))
            
        except Exception as failed_pole_genre_execution:
            logger(False, f"POLE EXECUTION FAILED: {failed_pole_genre_execution}")

    elif pole_end == "wishlist":
        return redirect(url_for("wishlist"))

    elif pole_end == "index":
        return redirect(url_for("index"))

    return redirect(url_for("product_information", id = catalogue_id))

@app.route("/remove_item/<string:album_name>", methods = ["POST"])
def remove_item(album_name):
    cart = get_entry("cart")

    if album_name in cart:
        remove_status = remove_specific_key(cart = album_name)

        if remove_status:
            flash(f"Removed all '{album_name}' in your cart")
    else:
        flash(f"'{album_name}' was not found in your cart or was already removed.")

    return redirect(url_for("cart"))

@app.route("/apply_changes", methods = ["POST"])
def apply_changes():
    album_products = load_data_products()
    cart = get_entry("cart")

    for n, items in cart.items():
        if items.get("is_unavailable"):
            continue

        # value validation
        try:
            max_quantity = album_products[n]["stock"] if album_products[n]["stock"] < 5 else 5
            qty = int(request.form[f"i-invn-{items['id']}"])

            if 0 < qty <= max_quantity and items['quantity'] != qty:
                cart[n]["quantity"] = (qty)
            elif qty > max_quantity:
                flash(f"({n}) That value should not exceed more than {max_quantity} maximum.")
            elif 0 >= qty:
                flash(f"({n}) That value should not be less than 1 minimum.")

        except ValueError as e:
            logger("NON-INTEGER VALUE", f"({n}) Non-integer detected", "closed_log")
            flash(f"({n}) Please enter a number to adjust that quantity.")

    save_entries(cart = cart)

    return redirect(url_for("cart"))

# adding/removing item to wishlist
@app.route("/toggle_wishlist/<catalogue_id>/<string:album_name>", defaults = {"pole_end": None, "force_removal": False}, methods = ["POST"])
@app.route("/toggle_wishlist/<catalogue_id>/<string:album_name>/<string:pole_end>/<force_removal>", methods = ["POST"])
def toggle_wishlist(catalogue_id, album_name, pole_end, force_removal):
    albums = load_data_products()
    wishlists = get_entry("wishlists")

    # 1. Check whether the requested catalogue ID exists.
    for _, mvt in albums.items():
        if catalogue_id.lower() == mvt["id"].lower():            
            break
    else:
        flash(f"Item '{catalogue_id}' could not be found. Double check that the catalogue ID exists.")
        return redirect(url_for("product_information", id = catalogue_id)) 

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

            save_entries(wishlists = wishlists)

            flash(f"{album_name} added to your wishlist")
            flash("%.show_panel_2;")
            flash({
                album_name: {
                    "id": albums[album_name]["id"],
                    "artist": albums[album_name]["artist"],
                    "image": albums[album_name]["image"],
                    "price": albums[album_name]["price"],
                }
            }) # key variables by item in order to show; critical for side panel key access

        else:
            wishlist_remove_status = remove_specific_key(wishlists = album_name)

            if wishlist_remove_status:
                flash(f"{album_name} removed from your wishlist")
    except:
        flash("Sorry, but there was a problem when we tried to adjust your wishlist. Try again later.")

    # pole end
    if pole_end == "wishlist":
        return redirect(url_for("wishlist"))

    return redirect(url_for("product_information", id = catalogue_id))

# Item Genre: display all items
@app.route("/category/item")
def category_all():
    get_albums = load_data_products()
    cart = verify_existing_product(get_albums, get_entry("cart"), "cart")
    key = panel_access_from_flash()
    result = item_display_by_genre() # get the result via genre
    _, pr = album_date_modules(get_albums, 1)

    return render_template("item_genre.html", genre = "all",
                           imported_data = result, cart = cart,
                           key_param = key, pr = pr)

# Item Genre: specific genre
@app.route("/category/item-<string:genre>")
def category(genre):
    result = item_display_by_genre(genre) # get the result via genre

    # Abort if the dictionary is empty.
    if result == {}:
        abort(404)

    get_albums = load_data_products()
    cart = verify_existing_product(get_albums, get_entry("cart"), "cart")
    key = panel_access_from_flash()
    _, pr = album_date_modules(get_albums, 1)

    return render_template("item_genre.html", genre = genre,
                           imported_data = result, cart = cart,
                           key_param = key, pr = pr)

# Item Genre: Filter Price Range
@app.route("/category/item-<string:genre>/<price_range>")
def category_price_filter(genre, price_range):
    result, gio = item_display_by_genre(None if genre == "all" else genre, price_range) # get the result via genre and price
    kebab_case_pxrange = f"{price_range}".replace("_", "-") # used for add to cart action to redirect back here

    # also connected if the price range exists
    text_value = px_range_post_inversion(price_range)
    text_value = text_value.lower() if not text_value == None else text_value

    # Abort if genre is not exist by gio = 0,
    # accessed through function item_display_by_genre;
    # also inexistent price range (typed by manual and in case of typos).
    if gio <= 0 or text_value == None:
        abort(404)

    get_albums = load_data_products()
    cart = verify_existing_product(get_albums, get_entry("cart"), "cart")
    key = panel_access_from_flash()
    _, pr = album_date_modules(get_albums, 1)

    return render_template("item_genre.html", genre = genre,
                           text_value = text_value, pxrange = kebab_case_pxrange,
                           imported_data = result, cart = cart,
                           key_param = key, pr = pr)

@app.route("/filter_price/<string:genre>", methods = ["POST"])
def filter_price(genre):
    selected_range = request.form["price-range"]

    # in snake case, naming convention
    srg = f"{selected_range.replace(' ', '_').replace('$', '')}".lower()

    # redirect with filtering item in price
    return(redirect(url_for("category_price_filter", genre = genre, price_range = srg)))

# Invoice Page
@app.route("/invoice-<int:inv_number>")
def invoice_selection(inv_number):
    # sqlite3 \
    try:
        with sqlite3.connect("order_history.db") as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM orders WHERE id = {inv_number}")
            rows = cursor.fetchall()[0] # fetching for one row only

            second_row = json.loads(rows[2])
            load_items = json.loads(rows[3])
            items_on_hold = {}
            items = {}
            
            # items on hold
            if rows[9]:
                items_on_hold = json.loads(rows[9])

            s = 0 # used for listing

            albums = load_data_products()
            _, pr = album_date_modules(albums, 1)
            key = panel_access_from_flash()

            # at index registration
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
        abort(404) # not found

    return render_template("invoice.html", albums = albums,
                           data = fetched_data, key_param = key,
                           pr = pr)

@app.route("/order_history")
def order_history():
    def check_error_strikes(orders):
        # logging message through full error strikes
        error_strikes = sum(1 if "error" in pr.keys() else 0 for pr in orders)
        if error_strikes == len(order_history_results):
            logger("ORDER HISTORY ERROR", "Strike reached fully due to persistent errors; order history table can't be displayed.")

    with sqlite3.connect("order_history.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM orders")

        # fetched data
        o_rows = cursor.fetchall()
        order_history_results = []

        # each ordered place from list on o_rows
        for orders in o_rows:
            order_id = orders[0]

            try:
                order_history_results.append({
                    "order_id": order_id,
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
                logger(False, f"({order_id}) {path_error} [received from order history route]", "closed_log")
                order_history_results.append({"error": str(path_error)})

        check_error_strikes(order_history_results)

    return render_template("order_history.html", orders = order_history_results)

# order History deletion
@app.route("/delete_invoice/<int:order_id>", methods = ["POST"])
def delete_invoice(order_id):
    with sqlite3.connect("order_history.db") as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))

            conn.commit()

            flash(f"({order_id}) Invoice deleted.")

        except sqlite3.Error as delete_invoice_error:
            conn.rollback()

            logger("DELETE INVOICE ERROR", delete_invoice_error)
            flash(f"Invoice #{order_id} deletion has been halted to due to error.")

    return redirect(url_for("order_history"))

@app.route("/cart")
def cart():
    albums = load_data_products()

    # Get cart via session.get
    cart = verify_existing_product(albums, get_entry("cart"), "cart")
    _, pr = album_date_modules(albums, 1)

    # Get price calculation
    __n, subtotal, gst, ship_fee, discount, __n2 = calculate_total(cart)

    return render_template("cart.html", cart = cart, albums = albums,
                           subtotal = subtotal, gst = gst, discount = discount,
                           pre_released = pr)

@app.route("/wishlist")
def wishlist():
    albums = load_data_products()
    key = panel_access_from_flash()
    cart, wishlists = get_entry("cart", "wishlists")
    _, pr = album_date_modules(albums, 1)

    cart = verify_existing_product(albums, cart, "cart")
    wishlists = verify_existing_product(albums, wishlists, "wishlists")

    return render_template("wishlist.html", cart = cart,
                           wishlists = wishlists, albums = albums,
                           key_param = key, pre_released = pr)

# Applying Coupons
@app.route("/apply_coupons", methods = ["POST"])
def apply_coupons():
    get_data_coupon = load_data_coupons() # get the data of the coupons
    input_coupon = request.form["coupon"] # get user's input

    try:
        sets_used_coupons = get_entry("used_coupons")

        # if coupon exists
        if input_coupon in get_data_coupon and not input_coupon in sets_used_coupons:

            if input_coupon in sets_used_coupons: # not already used
                save_entries(coupon = {
                    "name": input_coupon,
                    "discount": get_data_coupon[input_coupon]["discount"]
                }) # applying coupon into session

                flash("Coupon applied")

            else:
                flash("Oops! You've already used that coupon.")

        else:
            flash("Coupon does not exist")
            
    except Exception as apply_coupon_error:
        logger("APPLY COUPON ERROR:", apply_coupon_error)
        print("An error has occurred while trying to apply the coupon. Try again later.")

    return redirect(url_for("cart"))

@app.route("/remove_coupon", methods = ["POST"])
def remove_coupon():
    is_removed = remove_coupon_action()
    if is_removed:
        flash(f"Removed a coupon: {is_removed["removed_cpn_name"]}. You can still enter it unless or until you have used it.")

    return redirect(url_for("cart"))

@app.route("/checkout")
def checkout():
    cart, billing_info = get_entry("cart", "billing_info")
    total, subtotal, gst, ship_fee, discount, total_with_discount = calculate_total(cart)

    if not cart:
        flash("You don't have items in your cart yet; start shopping for your favourite music album.")
        return redirect(url_for("cart"))

    return render_template("checkout.html",
                           total = total, subtotal = subtotal,
                           gst = gst, ship_fee = ship_fee,
                           cart = cart, discount = discount,
                           total_with_discount = total_with_discount,
                           saved_billing_info = billing_info)

@app.route("/continue_to_review")
def continue_to_review():
    cart, billing_info = get_entry("cart", "billing_info")
    total, subtotal, gst, ship_fee, discount, total_with_discount = calculate_total(cart)

    # validation (in billing info, check if some detail(s) are missing, omitting postal code)
    if (not cart or not billing_info) or (None in billing_info.values()):
        if not billing_info or None in billing_info.values():
            flash("You are missing with important thing. Enter your billing details so we can track your order.")

        return redirect(url_for("checkout"))

    return render_template("checkout_review.html",
                           total = total, subtotal = subtotal, 
                           gst = gst, ship_fee = ship_fee,
                           cart = cart, discount = discount,
                           total_with_discount = total_with_discount,
                           saved_billing_info = billing_info)

@app.route("/continue_to_review/get", methods = ["POST"])
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

    save_entries(billing_info = billing_info)

    return(redirect(url_for("continue_to_review")))

# Placing Order
@app.route("/place_order", methods = ["POST"])
def place_order():
    cart, coupon, billing_info, sets_used_coupons = get_entry("cart", "coupon", "billing_info", "used_coupons")

    # check if the cart or billing info is not empty
    if (not cart or not billing_info) or (None in billing_info.values()):
        time.sleep(0.9)

        if not billing_info or None in billing_info.values(): # missing details
            flash("You are missing with important thing. Enter your billing details so we can track your order.")

        return redirect(url_for("checkout"))
    
    time.sleep(2.4) # time delay

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
            # either partial fulfillment or backorder process
            stock_related_cause = {}
            on_hold_items = update_stock(cart)

            for n in on_hold_items.keys():
                if not on_hold_items[n]["cause_of_demand"] == "pre_order":
                    stock_related_cause[n] = on_hold_items[n]

            if stock_related_cause:
                flash("%.show_panel_3;")
                flash(on_hold_items) # critical for side panel key access

            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (date, customer, items, subtotal, gst, ship_fee, discount, total_charges, items_on_hold)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice_date, json.dumps(customer),
                  json.dumps(cart), subtotal, gst,
                  ship_fee, discount, main_total,
                  json.dumps(on_hold_items)))
            conn.commit()

        except Exception as place_order_error:
            conn.rollback() # reverts the changes

            logger("PLACE ORDER ERROR", place_order_error)
            print(f"Something went wrong: {place_order_error}")

            return redirect(url_for("index"))
        
    # write an invoice in .txt version
    with open(invoice_filename, "w") as f:
        try:
            invoice_file = f"{invoice_filename}"
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
    
    flash("Order Completed")

    # spike coupon removal | adding to used_coupons
    try:
        if coupon:
            coupon_name = coupon["name"]

            # None as a placeholder
            # since there is nothing to refer or access their value
            sets_used_coupons[coupon_name] = None
            save_entries(used_coupons = sets_used_coupons)
    except:
        print("Unable to add coupon to used coupons.")

    # take out all items in cart, and coupon
    remove_key("cart", "coupon")

    # redirect user to invoice section
    try:
        with sqlite3.connect("order_history.db") as conn:
            # fetch for id only
            cursor.execute(f"SELECT * FROM orders WHERE date = '{invoice_date}'")
            lid = cursor.fetchall()[0] # fetching for one row only
            redirect_id = lid[0]

        return redirect(url_for("invoice_selection", inv_number = int(redirect_id)))
    
    except Exception as redirect_error:
        logger(False, f"Failed to redirect to invoice number:, {redirect_error}", "closed_log")

    return redirect(url_for("index"))

@app.route("/accounts/<measure>", defaults = {"subject": None})
@app.route("/accounts/<measure>/<subject>")
def signup_login(measure, subject):
    if not measure == "signup" and not measure == "login":
        abort(404) # not found

    # verify if the user was logged on
    accessed_logon = session.get("session_key", {})
    if accessed_logon.get("accessed"):
        return redirect(url_for("my_account"))

    return render_template("account_access.html", msr = measure, sbj = subject)

@app.route("/signup", defaults = {"get_subject": None}, methods = ["POST"])
@app.route("/signup/<get_subject>", methods = ["POST"])
def signup(get_subject):
    def save_billing_info(bld):
        try:
            save_entries(billing_info = bld)
        except Exception as billing_err:
            logger(False, f"Failed to save billing details to newly created account: {billing_err}", "closed_log")

    # leading whitespaces removed; capitalised words
    fname = request.form["new-fname"].strip().title()
    lname = request.form["new-lname"].strip().title()
    email = request.form["new-email"]
    password = request.form["new-password"]
    confirm_password = request.form["new-confirm-password"]

    billing_info = {
        "first_name": fname,
        "surname": lname,
        "email": email,
        "physical_address": None,
        "town": None,
        "postal_code": None
    }

    # full name
    name = f"{fname} {lname}"
    date = datetime.datetime.now().strftime("%Y-%m-%d")

    # Complete Registration to Database
    try:
        # verify a password
        if password == confirm_password:
            cart = session.get("cart", {})
            wishlists = session.get("wishlists", {})
            
            # Connect to SQLite3: accounts
            with sqlite3.connect("accounts.db") as conn:
                cursor = conn.cursor()
                cursor.execute(""" 
                    INSERT INTO accounts (date, name, email, password, items, wishlists, billing_info, applied_coupon, used_coupons)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (date, name, email,
                      password, json.dumps(cart),
                      json.dumps(wishlists), "{}", "{}", "{}"))

                conn.commit()

            signin_session(email, password)
            save_billing_info(billing_info)
            flash(f"Welcome, {name}!")

        else:
            flash("Your password does not matched the one you are trying to confirm. Verify that the password is the same as the one you created.")
            return redirect(url_for("signup_login", measure = 'signup', subject = get_subject))
        
    except Exception as signup_error:
        logger("SIGNUP ERROR", signup_error)
        flash(f"Something went wrong while we are trying to sign you up: {signup_error}")
        
        return redirect(url_for("index"))

    # redirect to checkout via "get_subject"
    if get_subject == "for_awaiting_checkout":
        return redirect(url_for("checkout"))

    return redirect(url_for("index"))

@app.route("/login", defaults = {"get_subject": None}, methods = ["POST"])
@app.route("/login/<get_subject>", methods = ["POST"])
def login(get_subject):
    email = request.form["lg-email"]
    password = request.form["lg-password"]

    try:
        signin_session(email, password, 1)

    except (NameError, ValueError) as err:
        flash(f"{err}")
        return redirect(url_for("signup_login", measure = 'login', subject = get_subject))
    
    except Exception as login_error:
        logger("LOGIN ERROR", login_error)
        flash("Oops! Something went wrong. Please try again later.")

        return redirect(url_for("signup_login", measure = 'login', subject = get_subject))

    # redirect to checkout via "get_subject"
    if get_subject == "for_awaiting_checkout":
        return redirect(url_for("checkout"))

    return redirect(url_for("index"))

@app.route("/accounts/my_account")
def my_account():
    has_session_key = session.get("session_key", {})
        
    # verify if the user was logged on
    if has_session_key.get("accessed"):
        return render_template("account_access.html", msr = None, sbj = None)
    
    return redirect(url_for("signup_login", measure = 'login'))

@app.route("/logout", methods = ["POST"])
def logout():
    session.pop("session_key", None) # revoke session account
    session.modified = True

    return redirect(url_for("signup_login", measure = 'login'))

if __name__ == "__main__":
    initialise_database()

    app.run(debug = True)