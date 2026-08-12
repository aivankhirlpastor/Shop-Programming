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

# ROUTES <------------------->
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/category/<int:m>")
def product_information(m):
    models = load_data_products()
    pack_data = None

    # Check whether the variable "m" matches with each of the model value,
    # then return a valid format for the outputs.
    for items, mv in models.items():
        print(int(m) == int(mv["model"]))
        if int(m) == int(mv["model"]):
            # Product
            product_name = items
            pack_data = mv

            break
    else:
        abort(404)

    print(product_name, pack_data["label"])
    # If the condition was passed, move on to prepare for the outputs.
    return render_template("product_info.html",
                           product_name = product_name, product = pack_data)

@app.route("/cart")
def cart():
    return render_template("cart.html")

# ==== dynamic route instance ==== #
# @app.route("/category/<string:genre>")
# def category(genre):
#     return genre

# [comes the last]
# if __name__ == 'main': checks if file is being run directly - only runs code if opened directly.
if __name__ == "__main__":
    app.run(debug = True)