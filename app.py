from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import json, datetime, sqlite3, re
import os
import sys

# create flask web app
app = Flask("__name__")
app.secret_key = "your-secret-key"

# functions
def load_data_products():
    with open("data/products.json") as product:
        return json.load(product)

def calculate_total(c):
    cart_total = sum(item["price"] * item["quantity"] for item in c.values())
    gst = cart_total * 0.15

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
                "model": mdl[product]["model"],
                "label": mdl[product]["label"],
                "genre": mdl[product]["genre"],
                "price": mdl[product]["price"],
                "quantity": qty,
            }

            # Update the session.
            session["cart"] = cart
            session.modified = True

            flash(f"({qty}) {product} added to cart.")
        else:
            flash(f"({product}) Item was already in cart.")
            
    else:
        # out of stock message
        flash(f"Sorry, but {product} ran out of stock.")

# ROUTES <------------------->
@app.route("/")
def index():
    load_models = load_data_products()

    return render_template("index.html", models = load_models)

@app.route("/category/item/<int:m>")
def product_information(m):
    models = load_data_products()
    pack_data = None

    # Check whether the variable "m" matches with each of the model int.
    for items, mv in models.items():
        # print(int(m) == int(mv["model"]))
        if int(m) == int(mv["model"]):
            # Product
            product_name = items
            pack_data = mv

            break
    else:
        abort(404)

    cart = session.get("cart", {})

    # Used for some modification for if this product is in the cart.
    if product_name in cart:
        current_item = cart[product_name]

    # If the condition was passed, move on to prepare for the outputs.
    return render_template("product_info.html",
                           product_name = product_name, product = pack_data,
                           already_in_cart = (product_name in cart),
                           item_in_hold = current_item if product_name in cart else False,
                           in_stock = (models[product_name]["stock"] > 0))

# Add to Cart Route
@app.route("/add_to_cart/<int:m_value><string:product_name>/<string:input_selector>/<pole_end>", methods = ["POST"])
def add_to_cart(m_value, product_name, input_selector, pole_end):
    model = load_data_products()

    try:
        # validate whether the number have entered a number
        quantity = int(request.form[input_selector])
        
        # 1. Check whether the variable "m" matches with each of the model int.
        for i, mvt in model.items():
            # If found and matched
            if int(m_value) == int(mvt["model"]):            
                break
        else:
            # If not... (INVALID)
            return "Item not found."

        # 2. Initiate an add to cart action.
        add_to_cart_action(model, product_name, quantity)
    except:
        flash("We could not add that item. Please enter a number in integer only.")

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
            for y in model.items():
                if str(genre_condition[0]).lower() == str(y[1]["genre"]).lower():
                    return redirect(url_for("category", genre = str(genre_condition[0]).lower()))                
        except Exception as err:
            print("Something went wrong. We can't transfer you back to the current genre of page:", err)

    return redirect(url_for("product_information", m = m_value))

@app.route("/remove_item/<int:ctg_number>/<string:album_name>", methods = ["POST"])
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
            qty = int(request.form[f"i-invn-{items['model']}"])

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
            # raise ValueError(f"Input {items['model']} is missing its value.")

    session["cart"] = cart
    session.modified = True

    return redirect(url_for("cart"))


@app.route("/category/item-<string:genre>")
def category(genre):
    model = load_data_products()
    stored_models = {}
    cart = session.get("cart", {})

    # Get all the products based on the genre given.
    for album_name, u in model.items():
        # One product's genre matches to <genre> adds to the dictionary.
        if str(genre).lower() == str(u["genre"]).lower():
            stored_models[album_name] = u
            stored_models[album_name]["in_cart"] = True if album_name in cart else False

    # Abort if the dictionary is empty.
    if stored_models == {}:
        abort(404)

    return render_template("item_genre.html", g = genre,
                           imported_data = stored_models, cart = cart)

@app.route("/cart")
def cart():
    albums = load_data_products()

    # Get cart via session.get
    cart = session.get("cart", {})

    # Get price calculation
    __n, subtotal, gst, ship_fee = calculate_total(cart)

    return render_template("cart.html", cart = cart, albums = albums,
                           subtotal = subtotal, gst = gst)

# temporary routes
@app.route("/visit", methods = ["POST"])
def visit():
    item_model = request.form['item_selector']

    return redirect(url_for("product_information", m = item_model))



# ==== dynamic route instance ==== #
# @app.route("/category/<string:genre>")
# def category(genre):
#     return genre

# [comes the last]
# if __name__ == 'main': checks if file is being run directly - only runs code if opened directly.
if __name__ == "__main__":
    app.run(debug = True)