from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
import json, datetime, sqlite3
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

# ROUTES <------------------->
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/category/item/<int:m>")
def product_information(m):
    models = load_data_products()
    pack_data = None

    # [ Check whether the variable "m" matches with each of the model value,
    # then return a valid format for the outputs. ]
    for items, mv in models.items():
        # print(int(m) == int(mv["model"]))
        if int(m) == int(mv["model"]):
            # Product
            product_name = items
            pack_data = mv

            break
    else:
        abort(404)

    # print(product_name, pack_data["label"])
    # Disable button of add-to-cart if product is in the cart.
    cart = session.get("cart", {})

    # Used for some modification for if this product is in the cart.
    if product_name in cart:
        current_item = cart[product_name]

    # If the condition was passed, move on to prepare for the outputs.
    return render_template("product_info.html",
                           product_name = product_name, product = pack_data,
                           already_in_cart = (product_name in cart),
                           item_in_hold = current_item if product_name in cart else False)

# Add to Cart Route
@app.route("/add_to_cart/<int:m_value><string:product_name>", methods=["POST"])
def add_to_cart(m_value, product_name):
    model = load_data_products()
    quantity = int(request.form["quantity"])

    # [ Check whether the variable "m" matches with each of the model value,
    # then return a valid format for the outputs. ]
    for i, mvt in model.items():
        # If found and matched
        if int(m_value) == int(mvt["model"]):            
            break
    else:
        # If not...
        return "Item not found."
        abort(404)

    # If the condition was passed, prompt the program to add items in cart.
    cart = session.get("cart", {})

    # Check whether the item is in cart already.
    if product_name not in cart:
        cart[product_name] = {
            "author": model[product_name]["author"],
            "model": model[product_name]["model"],
            "label": model[product_name]["label"],
            "genre": model[product_name]["genre"],
            "price": model[product_name]["price"],
            "quantity": quantity,
        }
    else:
        raise KeyError("Item is already at the cart.")

    # Update the session
    session["cart"] = cart
    session.modified = True

    return redirect(url_for("product_information", m = m_value))

@app.route("/cart")
def cart():
    models = load_data_products()

    # Get cart via session.get
    cart = session.get("cart", {})

    # Get price calculation
    __n, subtotal, gst, ship_fee = calculate_total(cart)


    return render_template("cart.html", cart = cart, model = models,
                           subtotal = subtotal, gst = gst)

# ==== dynamic route instance ==== #
# @app.route("/category/<string:genre>")
# def category(genre):
#     return genre

# [comes the last]
# if __name__ == 'main': checks if file is being run directly - only runs code if opened directly.
if __name__ == "__main__":
    app.run(debug = True)