// General elements
const configPanel = document.getElementById("config-bottom-bar");
const targetForm = document.getElementById("target-form");
const cancel = document.getElementById("cancel");
const save = document.getElementById("save-changes");

// Get the element of an input and p, classed "recalculation"
var getInputs = document.querySelectorAll("input[type=number]");
var getUnitPrices = document.querySelectorAll("p.price.recalculation");

// Get the invisible input elements
var getInvisibleInputs = document.querySelectorAll("input.input-pre-passing");
console.log(getInvisibleInputs);

// Additional Buttons
const submitBtn = document.querySelector("button.view-my-cart");

// array variables by their initials
let initialQuantity = [];
let unitPrice = [];
var isUnsavedChanges = false;

// functions
function revertChange(inp, iip, unp, index) {
    inp.classList.remove("modified");
    inp.value = initialQuantity[index];
    iip.value = initialQuantity[index];

    if (unp) {
        unp.innerHTML = `<sup>$</sup>${Math.round((unitPrice[index] * inp.value) * 100) / 100}`;
    }

    if (submitBtn) {
        submitBtn.disabled = false;
    }
}

for (let z = 0; z < getInputs.length; z++) {
    // local variable
    const i = getInputs[z];
    const u = getUnitPrices[z];

    // Check whether "u" is not undefined
    if (u !== undefined) {
        unitPrice.push(parseFloat(u.dataset.unitprice));
    }

    console.log((i.dataset.footing));

    // i.e. only works if the product is in the cart
    if (i.dataset.footing !== "True") {
        // immediately respond to changes
        i.addEventListener("input", e => {
            let mx = parseInt(i.max); // max value
    
            console.log(i.value, initialQuantity[z])
    
            if (parseInt(i.value) !== initialQuantity[z]) {
                isUnsavedChanges = true;
                i.classList.add("modified");
        
                console.log(i.value % 1, i.value % 1 == 0);
        
                // if condition to text changes
                if ((0 < i.value && i.value <= mx) && (i.value % 1 == 0) && u) {
                    u.innerHTML = `<sup>$</sup>${Math.round((unitPrice[z] * i.value) * 100) / 100}`;
                }
        
                if (!configPanel.classList.contains("arise")) {
                    configPanel.classList.add("arise");
                }
    
                if (submitBtn) {
                    submitBtn.disabled = true;
                }
    
                // changing the value of invisible input for the purpose of sending data to Python Flask
                const iid = `i-invn-${i.dataset.ctgnumber}`;
                document.getElementById(iid).value = i.value;
    
            } else {
                revertChange(i, getInvisibleInputs[z], u, z);
    
                // Automatic cancellation process
                let strike = 0;
                for (let rmn = 0; rmn < getInputs.length; rmn++) {
                    // search for elements with "modified" class
                    strike += !getInputs[rmn].classList.contains("modified") ? 1 : 0;
                }
    
                if (strike === getInputs.length) {
                    configPanel.classList.remove("arise");
                    isUnsavedChanges = false;
                }
            } 
        });
    }


    initialQuantity.push(Number(i.value));
}

// ----------- ADD EVENT LISTENERS
save.addEventListener("click", e => {
    isUnsavedChanges = false;
})

cancel.addEventListener("click", e => {
    // Cancellation Progress
    configPanel.classList.remove("arise");
    isUnsavedChanges = false;

    // forces all input to revert back to initial
    for (let h = 0; h < getInputs.length; h++) {
        // local variable
        const ii = getInputs[h];
        const pp = getInvisibleInputs[h];
        const uu = getUnitPrices[h];

        revertChange(ii, pp, uu, h);
    }
});

// window.addEventListener("load", e => {
//     // Get all the value for getInputs: for keyword as array
//     for (let l = 0; l < getInputs.length; l++) {

//         const il = getInputs[l];

//         if (il.value !== initialQuantity[l] ) {
//             il.value = initialQuantity[l];
//         }        
//     }
// })

window.addEventListener("beforeunload", e => {
    if (isUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
    }
});
