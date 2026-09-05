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
            CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password TEXT NOT NULL,
                    items TEXT,
                    wishlists TEXT,
                    billing_info TEXT
                    )
""")

def calculate_total(c):
    # round() and *100/100 rule to alleviate math float inaccuracy
    cart_total = sum((item["price"] * item["quantity"]) * 100 for item in c.values())
    cart_total = cart_total / 100

    gst = round(cart_total * 0.15, 2)

    # Shipping Fee: Determined by the amount of quantity
    quantity = sum(i["quantity"] for i in c.values())
    shipping_fee = 0

    return cart_total + gst + shipping_fee, cart_total, gst, shipping_fee

def add_to_cart_action(mdl, product, qty):
    cart = session.get("cart", {})

    if mdl[product]["stock"] > 0: # 3. Validate their stock

        if product not in cart: # Check whether the item is in cart already
            cart[product] = {
                "author": mdl[product]["author"],
                "id": mdl[product]["id"],
                "label": mdl[product]["label"],
                "genre": mdl[product]["genre"],
                "price": mdl[product]["price"],
                "quantity": qty,
            }

            # Update the session.
            session["cart"] = cart
            session.modified = True

            flash(f"({qty}) {product} added to cart.")

            # key variables by item in order to show
            key_var = {
                product: {
                    "author": mdl[product]["author"],
                    "price": mdl[product]["price"],
                    "quantity": qty,
                }
            }

            flash("%.show_panel;")
            flash(key_var) # critical for side panel key access
        else:
            flash(f"({product}) Item was already in cart.")
            
    else:
        # out of stock message
        flash(f"Sorry, but {product} ran out of stock.")

# panel access key function
def panel_access_from_flash():
    flash_syntax = get_flashed_messages() # as flash message
    post_key_access = {
        "show": True,
        "type": "show_specific_items", # for most of this project
        "by": {}
    }

    # print(35150, "o", flash_syntax)

    try:
        # regexp compilation
        show_panel_pattern = re.compile(r'%.show_panel', re.IGNORECASE)

        # execute section if contains flash message
        for m in range(len(flash_syntax)):
            matching_var = show_panel_pattern.search(str(flash_syntax[m]))

            # matching pair to proceed for returned key access
            if not matching_var:
                continue

            # get the dictionary after "%.show_panel" message 
            by_pair = flash_syntax[m + 1]

            print(True, "matched")
            print(by_pair)

            # Check if the adjacent obj is dictionary:
            if type(by_pair) is dict:
                for album_name, a in by_pair.items():
                    post_key_access["by"][album_name] = {
                        "author": a["author"],
                        "image": None,
                        "name": album_name,
                        "quantity": a["quantity"],
                        "total_price": a["price"] * a["quantity"],
                    }

                return post_key_access

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

    

def cart_amount():
    cart = session.get("cart", {})
    count = 0

    for _, n in cart.items():
        count += 1

    return count

# --------------------------------------

# POST variable declaration
# @app.before_request
# def before_request_function():
#     global key
    
#     key = {
#         "show": False, # replaceable by key-access function
#         "type": 0,
#         "by": {}
#     }

#     print(key)

# @app.after_request
# def after_request_function(r):
#     print("HEADING AFTER REQUEST", r.headers)
#     return r

# ROUTES <------------------->
@app.route("/")
def index():
    load_albums = load_data_products()
    ar, br, cr = index_album_modules()
    cart = session.get("cart", {})
    key = panel_access_from_flash()

    # blank {} is for the album items
    segment_modules = {
        "Latest Release": ar,
        "Featured": br,
        "Pre-Order": cr
    }

    # print(segment_modules)
    # c = cart_amount()
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

    cart = session.get("cart", {})
    key = panel_access_from_flash()
    print("135", key)

    # Used for some modification for if this product is in the cart.
    if album_name in cart:
        current_item = cart[album_name]

    # If the condition was passed, move on to prepare for the outputs.
    return render_template("product_info.html",
                           product_name = album_name, product = pack_data,
                           already_in_cart = (album_name in cart),
                           item_in_hold = current_item if album_name in cart else False,
                           in_stock = (albums[album_name]["stock"] > 0), key_param = key)

# Add to Cart Route
@app.route("/add_to_cart/<catalogue_id>/<string:product_name>/<string:input_selector>/<pole_end>", methods = ["POST"])
def add_to_cart(catalogue_id, product_name, input_selector, pole_end):
    albums = load_data_products()

    try:
        # validate whether the number have entered a number
        quantity = int(request.form[input_selector])
        
        # 1. Check whether the variable "id" matches with each of the album's ID.
        for i, mvt in albums.items():
            # If found and matched
            if catalogue_id.lower() == mvt["id"].lower():            
                break
        else:
            # If not... (INVALID)
            return "Item not found."

        # 2. Initiate an add to cart action.
        add_to_cart_action(albums, product_name, quantity)
    except Exception as e:
        flash("We could not add that item. Please enter a number in integer only.")
        raise Exception(e)

    # A pole_end is just another way whether to redirect the user back into grid display page after the action.
    # These pattern must correspond to the pole_end as string.
    redirect_to_grid_pattern = re.compile(r'^\d{1}[%][a-z-]+', re.IGNORECASE)
    genre_pattern = re.compile(r'[a-z-]+', re.IGNORECASE)

    redirect_condition = redirect_to_grid_pattern.findall(pole_end)
    genre_condition = genre_pattern.findall(pole_end)

    # redirect users back based on where they currently at
    if type(pole_end) == str and pole_end[0] == "1" and redirect_condition:
        # verify if there is an existing genre
        try:
            for y in albums.items():
                if str(genre_condition[0]).lower() == str(y[1]["genre"]).lower():
                    return redirect(url_for("category", genre = str(genre_condition[0]).lower()))                
        except Exception as err:
            print("Something went wrong. We can't transfer you back to the current genre of page:", err)
    elif pole_end == "index":
        return redirect(url_for("index"))

    return redirect(url_for("product_information", id = catalogue_id))

@app.route("/remove_item/<ctg_number>/<string:album_name>", methods = ["POST"])
def remove_item(ctg_number, album_name):
    cart = session.get("cart", {})

    if album_name in cart:
        del cart[album_name]
        session["cart"] = cart
        session.modified = True

        flash(f"Removed all '{album_name}' in your cart")
    else:
        flash(f"'{album_name}' was not found in your cart or was already removed.")

    return redirect(url_for("cart"))

@app.route("/apply_changes", methods = ["POST"])
def apply_changes():
    album_products = load_data_products()
    cart = session.get("cart", {})

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

        except Exception as e:
            print(e)
            flash(f"({n}) Please enter a number to adjust that quantity.")
            # raise ValueError(f"Input {items['id']} is missing its value.")

    session["cart"] = cart
    session.modified = True

    return redirect(url_for("cart"))

@app.route("/category/item-<string:genre>")
def category(genre):
    data_album = load_data_products()
    stored_data = {}
    cart = session.get("cart", {})
    key = panel_access_from_flash()

    # Get all the products based on the genre given.
    for album_name, u in data_album.items():
        # One product's genre matches to <genre> adds to the dictionary.
        if str(genre).lower() == str(u["genre"]).lower():
            stored_data[album_name] = u
            stored_data[album_name]["in_cart"] = True if album_name in cart else False

    # Abort if the dictionary is empty.
    if stored_data == {}:
        abort(404)

    return render_template("item_genre.html", g = genre,
                           imported_data = stored_data, cart = cart, key_param = key)

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
                    "author": m["author"],
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

@app.route("/cart")
def cart():
    albums = load_data_products()

    # Get cart via session.get
    cart = session.get("cart", {})

    # Get price calculation
    __n, subtotal, gst, ship_fee = calculate_total(cart)

    return render_template("cart.html", cart = cart, albums = albums,
                           subtotal = subtotal, gst = gst)

@app.route("/checkout")
def checkout():
    cart = session.get("cart", {})
    billing_info = session.get("billing_info", {}) # information retrieval in return

    total, subtotal, gst, ship_fee = calculate_total(cart)

    if not cart:
        flash("You don't have items in your cart yet; start shopping for your favourite music album.")
        return redirect(url_for("cart"))

    return render_template("checkout.html",
                           total = total, subtotal = subtotal,
                           gst = gst, ship_fee = ship_fee,
                           cart = cart, saved_billing_info = billing_info)

@app.route("/continue_to_review", methods = ["POST"])
def continue_to_review():
    cart = session.get("cart", {}) # get all the items in cart
    billing_info = session.get("billing_info", {}) # store within the session

    total, subtotal, gst, ship_fee = calculate_total(cart)

    # organising billing info in dictionary; get input values via "request.form"
    billing_info = {
        "first_name": request.form["first-name"],
        "surname": request.form["surname"],
        "email": request.form["email"],
        "physical_address": request.form["physical-addr"],
        "town": request.form["suburb"],
        "postal_code": request.form["postal-code"]
    }

    session["billing_info"] = billing_info

    # save Modification
    session.modified = True

    return render_template("checkout_review.html",
                           total = total, subtotal = subtotal, 
                           gst = gst, ship_fee = ship_fee,
                           cart = cart, saved_billing_info = billing_info)

# Info Retrieval
@app.route("/place_order", methods = ["POST"])
def place_order():
    # time delay
    time.sleep(2.4)

    # get "Carts" and "Billing Info" from the session
    cart = session.get("cart", {}) # get all the items in cart
    billing_info = session.get("billing_info", {}) # store within the session

    customer_name = f"{billing_info["first_name"]} {billing_info["surname"]}"
    customer = {
        "name": customer_name,
        "email": billing_info["email"],
        "physical_address": billing_info["physical_address"],
        "town": billing_info["town"],
        "postal_code": billing_info["postal_code"],
    }

    # check if the cart and billing info is not empty
    if not cart and not billing_info:
        return

    total, subtotal, gst, ship_fee = calculate_total(cart)
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
            """, (invoice_date, json.dumps(customer), json.dumps(cart), subtotal, gst, ship_fee, 0, total))

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

    try:
        3

    except Exception as e:
        return redirect(url_for("index"))

    # Updating the stock will be at the later sprint planning.
    flash("Order Completed")

    # redirect user to invoice section
    try:
        with sqlite3.connect("order_history.db") as conn:
            # fetch for id only
            cursor.execute(f"SELECT * FROM orders WHERE date = '{invoice_date}'")
            lid = cursor.fetchall()[0] # fetching for one row only
            redirect_id = lid[0]

        return redirect(url_for("invoice_selection", inv_number = int(redirect_id)))

    # in case that wasn't exist
    except Exception as err:
        print(err)

    return redirect(url_for("index"))

# temporary routes
@app.route("/visit", methods = ["POST"])
def visit():
    item_model = request.form['item_selector']

    return redirect(url_for("product_information", m = item_model))

@app.route("/accounts/<measure>", defaults = {"subject": None})
@app.route("/accounts/<measure>/<subject>")
def signup_login(measure, subject):

    if measure == "signup":
        print(2)
    elif measure == "login":
        print(1)
    else:
        # abort(404)
        raise Exception(f"Unknown measure: {measure}")

    return render_template("signup_and_login.html", msr = measure, sbj = subject)


# ==== dynamic route instance ==== #
# @app.route("/category/<string:genre>")
# def category(genre):
#     return genre

# [comes the last]
# if __name__ == 'main': checks if file is being run directly - only runs code if opened directly.
if __name__ == "__main__":

    initialise_database()

    app.run(debug = True)