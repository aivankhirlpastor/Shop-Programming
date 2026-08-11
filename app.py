from flask import Flask, render_template, request, redirect, url_for, session, flash
import json, datetime, sqlite3
import os
import sys

# create flask web app
app = Flask("__name__")
app.secret_key = "your-secret-key"

# ROUTES <------------------->
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/product")
def product_information():
    return render_template("product_info.html")

@app.route("/cart")
def cart():
    return render_template("cart.html")

# ==== dynamic route instance ==== #
@app.route("/category/<string:genre>")
def category(genre):
    return genre

# [comes the last]
# if __name__ == 'main': checks if file is being run directly - only runs code if opened directly.
if __name__ == "__main__":
    app.run(debug = True)