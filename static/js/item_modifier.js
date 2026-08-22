// General elements
const configPanel = document.getElementById("config-panel");
const cancel = document.getElementById("cancel");
const save = document.getElementById("save-changes");

// Get the element of an input and p, classed "recalculation"
const getInputs = document.querySelectorAll("input[type=number]");
const getUnitPrices = document.querySelectorAll("p.price.recalculation");

// array variables by their initials
let initialQuantity = [];
let unitPrice = [];

var isUnsavedChanges = false;

for (let z = 0; z < getInputs.length; z++) {
    // local variable
    const i = getInputs[z];
    const u = getUnitPrices[z];

    // Check whether "u" is not undefined
    if (u !== undefined) {
        unitPrice.push(parseFloat(u.dataset.unitprice));
    }

    // immediately respond to changes
    i.addEventListener("input", e => {
        isUnsavedChanges = true;
        i.classList.add("modified");

        // if condition to text changes
        if (i.value > 0) {
            u.textContent = `$${Math.round((unitPrice[z] * i.value) * 100) / 100}`
        }

        if (!configPanel.classList.contains("arise")) {
            configPanel.classList.add("arise");
        }
    });

    initialQuantity.push(Number(i.value));
}

// ----------- ADD EVENT LISTENERS
save.addEventListener("click", e => {
    isUnsavedChanges = false;
})

cancel.addEventListener("click", e => {
    // Cancellation Progress
    configPanel.classList.remove("arise");

    isUnsavedChanges = false // revert back to false

    // forces all input to revert back to initial
    for (let h = 0; h < getInputs.length; h++) {
        // local variable
        const ii = getInputs[h];
        const uu = getUnitPrices[h];

        ii.classList.remove("modified");
        ii.value = initialQuantity[h];
        uu.textContent = `$${Math.round((unitPrice[h] * ii.value) * 100) / 100}`
    }
});

window.addEventListener("load", e => {
    for (let l = 0; l < getInputs.length; l++) {

        const il = getInputs[l];

        if (il.value !== initialQuantity[l] ) {
            il.value = initialQuantity[l];
        }        
    }
})

window.addEventListener("beforeunload", e => {
    if (isUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
    }
});
