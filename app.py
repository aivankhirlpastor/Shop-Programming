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
    with open("data/products.json", "r") as product:
        album_data = json.load(product)

    for album_name, i in item.items():
        if album_name in album_data:

            album_data[album_name]["stock"]

# syntax building for database
def set_syntax_building(argument: dict|list|tuple, positional_value: list|tuple = ()):
    def initialise_build(params: dict) -> dict:
        if not type(params) is dict:
            raise TypeError(f"The argument or the parameter to initialising 'set' syntax structure is not in dict; got {type(params)}")

        # prompts
        key_terms = ["cart", "wishlists", "billing_info", "applied_coupon", "coupon", "used_coupons"]
        session_key = session.get("session_key", {})

        set_clause_structure = []
        set_clause_value = []

        for tr in params.keys():
            if tr in key_terms:
                # variant words or terms: cart/items, coupon/applied_coupon
                if tr == "cart":
                    term = "items"
                    term_key_session = "cart"
                elif tr == "coupon":
                    term, term_key_session = ["applied_coupon" for y in range(2)]
                else:
                    term, term_key_session = [tr for y in range(2)]

                # set syntax building prompt
                set_clause_structure.append(f"{term} = ?")
                set_clause_value.append(json.dumps(params[tr]))

                # unavailable session naming at that time
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
        raise TypeError("Main argument is an invalid type; it requires to be at dictionary, list, or tuple.")

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
            
            # update account session
            session["session_key"] = key_session
            session.modified = True
            
            conn.commit()

            # successful saving action
            return {
                "is_saved": "database",
                "status": 1
            }
            
        except sqlite3.Error as er:
            conn.rollback()
            print(f"Something went wrong: {er}")
            
            # unsuccessful saving action due to exception
            return None 
        
# Strict Searching in registered accounts;
# requires the variable 'name' to be listed
# under conditions.

# use 'get_entry' function when dealing with
# two sides
def get_entry(kyn_a):
    def issue_entries(name):
        result = []
        has_session_key = session.get("session_key", {})

        try:
            # guest account
            if not has_session_key:
                for tg in name:
                    v = session.get(tg, {})
                    result.append(v)

                return result
    
            # session with user being logged on
            else:
                with sqlite3.connect("accounts.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT * FROM accounts WHERE email = '{has_session_key["email"]}'")

                    post_identifier = cursor.fetchall()
                    main_row = post_identifier[0]

                    items = json.loads(main_row[5])
                    wishlists = json.loads(main_row[6])
                    billing_info = json.loads(main_row[7])
                    applied_coupon = json.loads(main_row[8])
                    used_coupons = json.loads(main_row[9])

                    # unpacking name; observe if "tr" is listed at "if-else"
                    for tr in name:
                        rar = {}

                        # observe if the 
                        if tr == "cart":
                            rar = items
                        elif tr == "wishlists":
                            rar = wishlists
                        elif tr == "billing_info":
                            rar = billing_info
                        elif tr == "applied_coupon" or tr == "coupon":
                            rar = applied_coupon
                        elif tr == "used_coupons":
                            rar = used_coupons

                        result.append(rar)

                    return result

        except Exception as R:
            result = []
            print(R)

            for err in name:
                result.append({}) # blanks

            return result

    # storing names for obtaining details individually
    # if "multiple name is given" | only one key provided
    get_pre_passing = kyn_a if type(kyn_a) is list else [kyn_a]
    ent = issue_entries(get_pre_passing) # get via session.get or database selection

    # returning stage
    if len(ent) == 1:
        return ent[0] # only one result provided

    # tuple
    return ent

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
            get_syntax_structure, get_syntax_value, returned_key_session = set_syntax_building(kwargs)

            # the prompt below was made first before creating set_syntax_building()
            # -------------------------------------------------------------
            # for tr in kwargs.keys():
            #     if tr in key_terms:
            #         # variant words or terms: cart/items, coupon/applied_coupon
            #         if tr == "cart":
            #             term = "items"
            #             term_key = "cart"
            #         elif tr == "coupon":
            #             term, term_key = ["applied_coupon" for y in range(2)]
            #         else:
            #             term, term_key = [tr for y in range(2)]

            #         # set syntax building
            #         set_clause_structure.append(f"{term} = ?")
            #         set_clause_value.append(json.dumps(kwargs[tr]))

            #         # unavailable session naming at that time
            #         if not tr == "wishlists" or not tr == "billing_info":
            #             has_session_key[term_key] = kwargs[tr]


            #     # checks if "tr" is listed below: tr == "<column_name>"
            #     if tr == "cart":
            #         set_clause_structure.append("items = ?")
            #         set_clause_value.append(json.dumps(value))

            #         has_session_key["cart"] = value

            #     elif tr == "wishlists":
            #         set_clause_structure.append("wishlists = ?")
            #         set_clause_value.append(json.dumps(value))

            #         # has_session_key["wishlists"] = value

            #     elif tr == "billing_info":
            #         set_clause_structure.append("billing_info = ?")
            #         set_clause_value.append(json.dumps(value))

            #         # has_session_key["billing_info"] = value

            #     elif tr == "applied_coupon" or tr == "coupon":
            #         set_clause_structure.append("applied_coupon = ?")
            #         set_clause_value.append(json.dumps(value))

            #         has_session_key["applied_coupon"] = value

            #     elif tr == "used_coupons":
            #         set_clause_structure.append("used_coupons = ?")
            #         set_clause_value.append(json.dumps(value))

            #         has_session_key["used_coupons"] = value

            # updating database table
            return make_change_to_database(get_syntax_structure, get_syntax_value, returned_key_session)

    except Exception as R:
        raise Exception(f"Something went wrong: {R}")

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

            get_syntax_structure, get_syntax_value, returned_key_session = set_syntax_building(tuple(kwargs.keys()), value_to_save)
            return make_change_to_database(get_syntax_structure, get_syntax_value, returned_key_session)
            
    except Exception as R:
        flash(f"Something went wrong while deleting: {R}")
        raise Exception(f"Something went wrong while deleting: {R}")

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
            get_syntax_structure, get_syntax_value, returned_key_session = set_syntax_building(args, ({},) * len(args))
            return make_change_to_database(get_syntax_structure, get_syntax_value, returned_key_session)

    except Exception as R:
        print(f"Something went wrong while deleting: {R}")
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

            # not matched
            if not password == uid[4]:
                raise ValueError("Password is incorrect.")

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
            # if account associated with email was not found; post_identifier is empty
            raise NameError(f"Account was not found: {email}")

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
        # cpn_name = session.get("coupon", {})["name"] # get the name first
        cpn_name = get_entry("coupon")["name"] # get the name first
        removal_status = remove_key("coupon")

        if not removal_status:
            return

        # session.pop("coupon", None) # coupon removal via session.pop
        # session.modified = True
    except Exception as r:
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
    except:
        pass

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
        # One product's genre matches to <genre> adds to the dictionary.

        # price range
        if (str(gnr).lower() == str(u["genre"]).lower()) or gnr == None:
            io += 1 # add 1 if genre exists by checking item's genre

            if check_price_range(u["price"]):
                # None = display all items
                stored_data[album_name] = u
                stored_data[album_name]["in_cart"] = True if album_name in c else False

    # pass the result back to variable
    if not px_range == None:
        return stored_data, io # tuple

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
    # cart = session.get("cart", {})
    cart = get_entry("cart")

    if mdl[product]["stock"] > 0: # 3. Validate their stock

        if product not in cart: # Check whether the item is in cart already
            cart[product] = {
                "artist": mdl[product]["artist"],
                "id": mdl[product]["id"],
                "label": mdl[product]["label"],
                "genre": mdl[product]["genre"],
                "price": mdl[product]["price"],
                "quantity": qty,
            }

            # Update the session.
            save_entries(cart = cart)
            # session["cart"] = cart
            # session.modified = True

            flash(f"({qty}) {product} added to cart.")

            # key variables by item in order to show
            key_var = {
                product: {
                    "id": mdl[product]["id"],
                    "artist": mdl[product]["artist"],
                    "price": mdl[product]["price"],
                    "quantity": qty,
                }
            }

            flash("%.show_panel_1;")
            flash(key_var) # critical for side panel key access
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
            return aa["quantity"], a["price"] * a["quantity"]

        # 2 = Item Added to Wishlist    
        elif wn == 2:
            return 1, a["price"]

    flash_syntax = get_flashed_messages() # as flash message
    formulate_key_access = {
        "show": True,
        "type": "show_specific_items", # for most of this project
        "when": 0,
        "by": {}
    }

    # print(35150, "o", flash_syntax)

    try:
        # regexp compilation
        show_panel_pattern = re.compile(r'%.show_panel', re.IGNORECASE)
        when_pattern = re.compile(r'_\d+', re.IGNORECASE)

        # execute section if contains flash message
        for m in range(len(flash_syntax)):
            matching_var = show_panel_pattern.findall(str(flash_syntax[m]))
            when_var = when_pattern.findall(str(flash_syntax[m]))

            # matching pair to proceed for returned key access
            if not matching_var:
                continue

            # get the dictionary after "%.show_panel" message 
            by_pair = flash_syntax[m + 1]

            print(True, "matched")
            print(by_pair)

            # Check if the adjacent obj is dictionary:
            if not type(by_pair) is dict:
                continue

            # when 1, 1 = adding item to cart; when 2, 2 = adding item to wishlist
            when_int = int(f"{when_var[0]}".replace("_", ""))
            formulate_key_access["when"] = when_int

            for album_name, a in by_pair.items():
                qty, price = when_collection(when_int, a)
                formulate_key_access["name"] = album_name
                formulate_key_access["id"] = a["id"]

                formulate_key_access["by"][album_name] = {
                    "artist": a["artist"],
                    "image": None,
                    "name": album_name,
                    "quantity": qty,
                    "price": price
                }
                        
            return formulate_key_access

    except Exception as e:
        print("Failed to initiate side panel order:", e)
        return None

def index_album_modules():
    ach = load_data_products()

    ahr = {}
    bhr = {}
    chr = {}

    day_released = 10
    day_prereleased = 14

    # ------------------------------
    day_current = 20
    rlsd = 10
    pre_rlsd = 14

    current = datetime.datetime(2026, 4, day_current)
    date_pattern = re.compile(r'(\d{2})-(\d{2})-(\d{4})')

    for n, albm in ach.items():
        album_id = albm["id"]
        dz = albm["release_date"] # date

        # "ID" segment pattern
        id_prime_ptrn = re.compile(r'^\d{3}') # first segment
        id_mid_ptrn = re.compile(r'\d{4}') # middle segment

        # 'before' integer variable
        pdx, pmx, pyx = date_pattern.findall(dz)[0]
        pre_id_prime = id_prime_ptrn.findall(album_id)
        pre_id_mid = id_mid_ptrn.findall(album_id)

        # Turning string into integers to be calculatable
        dx, mx, yx = int(pdx), int(pmx), int(pyx)
        id_prime, id_mid = int(pre_id_prime[0]), int(pre_id_mid[0])
        album_release_date = datetime.datetime(yx, mx, dx)

        # testing for variable
        prereleased = album_release_date - timedelta(days = pre_rlsd)

        if n == "Little Life":
            print(prereleased.timestamp())
            diff = current - album_release_date
            print(diff.days)
            print(prereleased, "\n-------------------------------")

        # latest release
        if 0 <= (current - album_release_date).days <= rlsd:
            ahr[n] = albm

        # featured > calculated value == remainder
        elif (id_mid // day_current % 10) == (id_prime % 10):
            bhr[n] = albm

        # pre-released
        elif pre_rlsd >= (album_release_date - current).days > 0:
            chr[n] = albm
    
    # print(re.sub(r"-", " ", current_date)) # 

    # latest release (show until 14 days away)

    return ahr, bhr, chr

# --------------------------------------

# PRE variable declaration \ via research
@app.before_request
def before_load_function():

    # coupon validity
    if session.get("coupon", {}):
        coupon_validity()

@app.after_request
def after_request_function(req):

    # # main session_key
    # session_key = session.get("session_key", {})

    # cart = session.get("cart", {})
    # coupon = session.get("coupon", {})
    # sets_used_coupons = session.get("used_coupons", {})

    # try:
    #     # access to name
    #     if session_key:
    #         # updating the cart key | disimilarities between keys
    #         if not cart == session_key["cart"]:
    #             session_key["cart"] = cart

    #         # updating the coupon key | disimilarities between keys
    #         if not coupon == session_key["applied_coupon"]:
    #             session_key["applied_coupon"] = coupon

    #         # updating the sets of used coupons key | disimilarities between keys

    #         if not sets_used_coupons == session_key["used_coupons"]:
    #             session_key["used_coupons"] = sets_used_coupons

    #         # update account session
    #         session["session_key"] = session_key
    #         session.modified = True

    #         # altering the table
    #         with sqlite3.connect("accounts.db") as conn:
    #             cursor = conn.cursor()
    #             cursor.execute(f"""
    #                 UPDATE accounts
    #                 SET items = ?, applied_coupon = ?, used_coupons = ?
    #                 WHERE name = '{session_key["name"]}' 
    #             """, (json.dumps(session_key["cart"]),
    #                   json.dumps(session_key["applied_coupon"]),
    #                   json.dumps(session_key["used_coupons"]),))
    # except:
    #     pass

    # print("HEADING AFTER REQUEST", req.headers)
    return req

# --------------------------------------

# ROUTES <------------------->
@app.route("/")
def index():
    load_albums = load_data_products()
    ar, br, cr = index_album_modules()
    cart = get_entry("cart")
    key = panel_access_from_flash()

    # blank {} is for the album items
    segment_modules = {
        "Latest Release": ar,
        "Featured": br,
        "Pre-Order": cr
    }

    # print(segment_modules)
    return render_template("index.html", albums = load_albums,
                           segment_modules = segment_modules, cart = cart,
                           key_param = key)

@app.route("/category/item/<id>")
def product_information(id):
    albums = load_data_products()
    pack_data = None

    # Check whether the variable "id" matches with each of the album's ID.
    for items, mv in albums.items():
        # print(int(m) == int(mv["model"]))
        if id.lower() == mv["id"].lower():
            # Product
            album_name = items
            pack_data = mv

            break
    else:
        abort(404)

    cart, wishlists = get_entry(["cart", "wishlists"])
    key = panel_access_from_flash()
    print("135", key)

    # Used for some modification to input value if this product is in the cart.
    if album_name in cart:
        current_item = cart[album_name]

    # If the condition was passed, move on to prepare for the outputs.
    return render_template("product_info.html",
                           product_name = album_name, in_wishlists = (album_name in wishlists),
                           product = pack_data, already_in_cart = (album_name in cart),
                           item_in_hold = current_item if album_name in cart else False,
                           in_stock = (albums[album_name]["stock"] > 0), key_param = key)

# Add to Cart Route
@app.route("/add_to_cart/<catalogue_id>/<string:product_name>/<string:input_selector>/<pole_end>", methods = ["POST"])
def add_to_cart(catalogue_id, product_name, input_selector, pole_end):
    albums = load_data_products()

    try:
        # when input is not applicable, default is (<input_selector> in int * -1)
        if int(input_selector) <= -1:
            quantity = int(input_selector) * -1
        else:
            # validate whether the user have entered a number
            quantity = int(request.form[input_selector])
        
        # 1. Check whether the variable "id" matches with each of the album's ID.
        for _, mvt in albums.items():
            # If found and matched
            if catalogue_id.lower() == mvt["id"].lower():            
                break
        else:
            # If not... (INVALID)
            return "Item not found."

        # 2. Initiate an add to cart action.
        add_to_cart_action(albums, product_name, quantity)
    except ValueError as e:
        flash("We could not add that item. Please enter a number in integer only.")

    # A pole_end is just another way whether to redirect the user back into grid display page after the action.
    # These pattern must correspond to the pole_end as string.
    redirect_to_grid_pattern = re.compile(r'^\d{1}[%][a-z-]+', re.IGNORECASE)
    genre_pattern = re.compile(r'[a-z0-9-]+', re.IGNORECASE)

    redirect_condition = redirect_to_grid_pattern.findall(pole_end) # get a number
    genre_condition = genre_pattern.findall(pole_end)

    # redirect users back based on where they currently at (in case to item grid display)
    if type(pole_end) == str and pole_end[0] == "1" and redirect_condition:
        # for genre_condition as list*, [1] is used to take only the genre.
        gn = str(genre_condition[1]).lower()
        
        # for "category" validate if has price_range included; index [2] for price_range
        try:
            # [2] + converting kebab case into snake case
            has_px_range = f"{genre_condition[2]}".replace("-", "_")
        except:
            has_px_range = False

        try:
            if gn == "all":
                if not has_px_range:
                    return redirect(url_for("category_all"))

                # to the category w/ price-range filter
                return redirect(url_for("category_price_filter", genre = "all", price_range = has_px_range))
            
            for y in albums.items():

                # verify if there is an existing genre
                if gn == str(y[1]["genre"]).lower():
                    if not has_px_range:
                        return redirect(url_for("category", genre = gn))

                    # to the category w/ price-range filter
                    return redirect(url_for("category_price_filter", genre = gn, price_range = has_px_range))
            
        except Exception as err:
            print("Something went wrong. We can't transfer you back to the current genre of page:", err)
    elif pole_end == "wishlist":
        return redirect(url_for("wishlist"))
    elif pole_end == "index":
        return redirect(url_for("index"))

    return redirect(url_for("product_information", id = catalogue_id))

@app.route("/remove_item/<ctg_number>/<string:album_name>", methods = ["POST"])
def remove_item(ctg_number, album_name):
    cart = get_entry("cart")

    if album_name in cart:
        # del cart[album_name]
        # session["cart"] = cart
        # session.modified = True
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
                # raise Exception("The value is out of range.")

        except ValueError as e:
            print(e)
            flash(f"({n}) Please enter a number to adjust that quantity.")
            # raise ValueError(f"Input {items['id']} is missing its value.")

    save_entries(cart = cart)
    # session["cart"] = cart
    # session.modified = True

    return redirect(url_for("cart"))

# adding/removing item to wishlist
@app.route("/toggle_wishlist/<catalogue_id>/<string:album_name>", defaults = {"pole_end": None}, methods = ["POST"])
@app.route("/toggle_wishlist/<catalogue_id>/<string:album_name>/<string:pole_end>", methods = ["POST"])
def toggle_wishlist(catalogue_id, album_name, pole_end):
    albums = load_data_products()
    wishlists = get_entry("wishlists")

    # 1. Check whether the variable "id" matches with each of the album's ID.
    for _, mvt in albums.items():
        # If found and matched
        if catalogue_id.lower() == mvt["id"].lower():            
            break
    else:
        # If not... (INVALID)
        return "Item not found."

    # 2. Toggle item; either add or remove
    if album_name not in wishlists:
        wishlists[album_name] = {
            "artist": albums[album_name]["artist"],
            "id": albums[album_name]["id"],
            "label": albums[album_name]["label"],
            "genre": albums[album_name]["genre"],
            "price": albums[album_name]["price"]
        }

        save_entries(wishlists = wishlists)
        flash(f"{album_name} added to your wishlist")

        # key variables by item in order to show
        key_var = {
            album_name: {
                "id": albums[album_name]["id"],
                "artist": albums[album_name]["artist"],
                "price": albums[album_name]["price"],
            }
        }

        flash("%.show_panel_2;")
        flash(key_var) # critical for side panel key access

    else:
        wishlist_remove_status = remove_specific_key(wishlists = album_name)

        if wishlist_remove_status:
            flash(f"{album_name} removed to your wishlist")

    # pole end
    if pole_end == "wishlist":
        return redirect(url_for("wishlist"))

    return redirect(url_for("product_information", id = catalogue_id))

# Item Genre: display all items
@app.route("/category/item")
def category_all():
    cart = get_entry("cart")
    key = panel_access_from_flash()
    result = item_display_by_genre() # get the result via genre

    return render_template("item_genre.html", genre = "all",
                           imported_data = result, cart = cart, key_param = key)

# Item Genre: specific genre
@app.route("/category/item-<string:genre>")
def category(genre):
    cart = get_entry("cart")
    key = panel_access_from_flash()
    result = item_display_by_genre(genre) # get the result via genre

    # Abort if the dictionary is empty.
    if result == {}:
        abort(404)

    return render_template("item_genre.html", genre = genre,
                           imported_data = result, cart = cart, key_param = key)

# Item Genre: Filter Price Range
@app.route("/category/item-<string:genre>/<price_range>")
def category_price_filter(genre, price_range):
    cart = get_entry("cart")
    key = panel_access_from_flash()
    result, gio = item_display_by_genre(None if genre == "all" else genre, price_range) # get the result via genre and price
    kebab_case_pxrange = f"{price_range}".replace("_", "-") # used for add to cart action to redirect back here

    # also connected if the price range exists
    text_value = px_range_post_inversion(price_range)

    # lowercase
    text_value = text_value.lower() if not text_value == None else text_value

    # Abort if genre is not exist by gio = 0,
    # accessed through function item_display_by_genre;
    # also inexistent price range (typed by manual and in case of typos).
    if gio <= 0 or text_value == None:
        abort(404)

    return render_template("item_genre.html", genre = genre,
                           imported_data = result, cart = cart, key_param = key,
                           text_value = text_value, pxrange = kebab_case_pxrange)

@app.route("/filter_price/<string:genre>", methods = ["POST"])
def filter_price(genre):
    selected_range = request.form["price-range"]

    # in snake case, naming convention
    srg = f"{selected_range.replace(' ', '_').replace('$', '')}".lower()

    # destination to HTML page of filtering item in price
    return(redirect(url_for("category_price_filter", genre = genre, price_range = srg)))

# Invoice Page
@app.route("/invoice-<int:inv_number>")
def invoice_selection(inv_number):
    # sqlite3 \
    try:
        with sqlite3.connect("order_history.db") as conn:
            cursor = conn.cursor()

            # \fetch
            cursor.execute(f"SELECT * FROM orders WHERE id = {inv_number}")
            rows = cursor.fetchall()[0] # fetching for one row only

            second_row = json.loads(rows[2])
            load_items = json.loads(rows[3])
            items = {}

            s = 0 # used for listing

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
                "total_charges": rows[8]
            }

            # raise Exception(fetched_data["customer"])

    # usually might suggest that the "id" is not exist
    except IndexError as index_err:
        abort(404) # not found

    except Exception as err:
        # sys.exit("Process aborted.")
        raise Exception(f"Can't redirect you with the invoice number {inv_number}: {err}")

    # return for template
    return render_template("invoice.html", data = fetched_data)

@app.route("/order_history")
def order_history():
    # results
    with sqlite3.connect("order_history.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM orders")

        # fetched data
        o_rows = cursor.fetchall()
        order_history_results = []

        # each ordered place from list on o_rows
        for orders in o_rows:
            # adding it into list of order_history_results
            order_history_results.append({
                "order_id": orders[0],
                "date": orders[1],
                "customer": json.loads(orders[2]),
                "items": json.loads(orders[3]),
                "subtotal": orders[4],
                "gst": orders[5],
                "ship_fee": orders[6],
                "discount": orders[7],
                "total_charges": orders[8],
            })

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
        except sqlite3.Error as e:
            conn.rollback()
            flash(f"Invoice #{order_id} deletion has been halted to due to error.")

    return redirect(url_for("order_history"))

@app.route("/cart")
def cart():
    albums = load_data_products()

    # Get cart via session.get
    # cart = session.get("cart", {})
    cart = get_entry("cart")

    # Get price calculation
    __n, subtotal, gst, ship_fee, discount, __n2 = calculate_total(cart)

    return render_template("cart.html", cart = cart, albums = albums,
                           subtotal = subtotal, gst = gst, discount = discount)

@app.route("/wishlist")
def wishlist():
    albums = load_data_products()
    key = panel_access_from_flash()
    cart, wishlists = get_entry(["cart", "wishlists"])

    return render_template("wishlist.html", cart = cart,
                           wishlists = wishlists, albums = albums,
                           key_param = key)

# Applying Coupons
@app.route("/apply_coupons", methods = ["POST"])
def apply_coupons():
    get_data_coupon = load_data_coupons() # get the data of the coupons
    input_coupon = request.form["coupon"] # get user's input

    # coupon = session.get("coupon", {})
    # sets_used_coupons = session.get("used_coupons", {})
    # Get coupon and used coupons via get_entry function
    coupon, sets_used_coupons = get_entry(["coupon", "used_coupons"])

    # if coupon exists and already used
    if input_coupon in get_data_coupon and not input_coupon in sets_used_coupons:

        # applying coupon into session
        coupon = {
            "name": input_coupon,
            "discount": get_data_coupon[input_coupon]["discount"]
        }

        # Update the session.
        # session["coupon"] = coupon
        # session.modified = True
        save_entries(coupon = coupon)

        # debugging
        flash(f"{input_coupon}: {get_data_coupon[input_coupon]["discount"]}")
        flash("Coupon applied")

    elif input_coupon in sets_used_coupons:
        flash("Oops! You've already used that coupon.")
    else:
        flash("Coupon does not exist")

    return redirect(url_for("cart"))

@app.route("/remove_coupon", methods = ["POST"])
def remove_coupon():
    is_removed = remove_coupon_action()
    if is_removed:
        # display flash message if successfully removed
        flash(f"Removed a coupon: {is_removed["removed_cpn_name"]}. You can still enter it unless or until you have used it.")

    return redirect(url_for("cart"))

@app.route("/checkout")
def checkout():
    # cart = session.get("cart", {})
    # billing_info = session.get("billing_info", {}) # information retrieval in return

    cart, billing_info = get_entry(["cart", "billing_info"])
    total, subtotal, gst, ship_fee, discount, total_with_discount = calculate_total(cart)

    if not cart:
        flash("You don't have items in your cart yet; start shopping for your favourite music album.")
        return redirect(url_for("cart"))

    return render_template("checkout.html",
                           total = total, subtotal = subtotal,
                           gst = gst, ship_fee = ship_fee,
                           cart = cart, saved_billing_info = billing_info,
                           discount = discount, total_with_discount = total_with_discount)

@app.route("/continue_to_review")
def continue_to_review():
    # cart = session.get("cart", {}) # get all the items in cart
    # billing_info = session.get("billing_info", {}) # store within the session
    cart, billing_info = get_entry(["cart", "billing_info"])
    total, subtotal, gst, ship_fee, discount, total_with_discount = calculate_total(cart)

    if not cart or not billing_info:
        if not billing_info:
            flash("You are missing with important thing. Enter your billing details so we are able to track your order.")
    
        return redirect(url_for("checkout"))

    return render_template("checkout_review.html",
                           total = total, subtotal = subtotal, 
                           gst = gst, ship_fee = ship_fee,
                           cart = cart, saved_billing_info = billing_info,
                           discount = discount, total_with_discount = total_with_discount)

@app.route("/continue_to_review/get", methods = ["POST"])
def get_details():
    billing_info = get_entry("billing_info") # store within the session

    # organising billing info in dictionary; get input values via "request.form"
    billing_info = {
        "first_name": request.form["first-name"],
        "surname": request.form["surname"],
        "email": request.form["email"],
        "physical_address": request.form["physical-addr"],
        "town": request.form["suburb"],
        "postal_code": request.form["postal-code"]
    }

    # session["billing_info"] = billing_info
    # session.modified = True # save Modification
    save_entries(billing_info = billing_info)

    return(redirect(url_for("continue_to_review")))

# Placing Order
@app.route("/place_order", methods = ["POST"])
def place_order():
    cart, coupon, billing_info, sets_used_coupons = get_entry(["cart", "coupon", "billing_info", "used_coupons"])

    # check if the cart or billing info is not empty
    if not cart or not billing_info:
        time.sleep(0.9)

        if not billing_info:
            flash("You are missing with important thing. Enter your billing details so we are able to track your order.")

        return redirect(url_for("checkout"))
    
    # time delay
    time.sleep(2.4)

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
    # invoice number will be declared as soon as we get to the database variables.

    # Save order history to SqLite Database
    try:
        with sqlite3.connect("order_history.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (date, customer, items, subtotal, gst, ship_fee, discount, total_charges)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice_date, json.dumps(customer), json.dumps(cart), subtotal, gst, ship_fee, discount, main_total))

            conn.commit()

        # write an invoice in .txt version
        invoice_file = f"{invoice_date}.txt"
        with open("invoice_file.txt", "w") as f:
            f.write("<-----> The Music Shop <----->\n")

            f.write(f"Invoice Number: {invoice_date}\n")
            f.write(f"Customer Name: {customer_name}\n")
            f.write(f"Date: {invoice_date}\n\n")

            f.write(f"Items:\n\n")

            for album_name, m in cart.items():
                f.write(f"-- {album_name}: {m["quantity"]} x ${m["price"]} = ${m["quantity"] * m["price"]:.2f}\n")

            f.write(f"Subtotal: ${subtotal:.2f}\n") if subtotal else None
            f.write(f"Subtotal: ${gst:.2f}\n") if gst else None
            f.write(f"Subtotal: ${ship_fee:.2f}\n\n") if ship_fee else None
            f.write(f"Subtotal: ${total:.2f}\n")

    # Except argument and return to home page
    except Exception as place_order_error:
        flash("Sorry, but we can't process your order right now.")
        flash(place_order_error)

        return redirect(url_for("index"))
    
    # Updating the stock will be at the later sprint planning.
    flash("Order Completed")

    # spike coupon removal | adding to used_coupons
    try:
        if coupon:
            coupon_name = coupon["name"]
            # * To Coupon name; None as a placeholder
            # since there is nothing to refer or access their value
            sets_used_coupons[coupon_name] = None
            save_entries(used_coupons = sets_used_coupons)

            # session["used_coupons"] = sets_used_coupons
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
    
    except Exception as err:
        # in case that wasn't exist
        print(err)

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
    # leading whitespaces removed; capitalised words
    fname = request.form["new-fname"].strip().title()
    lname = request.form["new-lname"].strip().title()
    email = request.form["new-email"]
    password = request.form["new-password"]
    confirm_password = request.form["new-confirm-password"]

    # full name
    name = f"{fname} {lname}"
    date = datetime.datetime.now().strftime("%Y-%m-%d")

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
                    INSERT INTO accounts (date, name, email, password, items, wishlists, billing_info, applied_coupon, used_coupons)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (date, name, email, password, json.dumps(cart), json.dumps(wishlists), "{}", "{}", "{}"))

                conn.commit()

            signin_session(email, password)
            flash(f"Welcome, {name}!")

        else:
            flash("Your password does not matched the one you are trying to confirm. Verify that the password is the same as the one you created.")
            return redirect(url_for("signup_login", measure = 'signup', subject = get_subject))
        
    except Exception as r:
        flash(f"Something went wrong while we handle you to sign up: {r}")

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

        # return to log in page
        return redirect(url_for("signup_login", measure = 'login', subject = get_subject))
    except Exception as error_for_debug:
        print(error_for_debug) # display error message on terminal output
        flash("Something went wrong. Please try again later.")

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

# ==== dynamic route instance ==== #
# @app.route("/category/<string:genre>")
# def category(genre):
#     return genre

# [comes the last]
# if __name__ == 'main': checks if file is being run directly - only runs code if opened directly.
if __name__ == "__main__":

    initialise_database()

    app.run(debug = True)