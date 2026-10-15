// get the element of an input
var getInputs = document.querySelectorAll("input[type=number]");

for (let iz = 0; iz < getInputs.length; iz++) {
    const i = getInputs[iz];

    let addBtn = document.getElementById(`add-${i.dataset.ctgnumber}`); /* all inputs must contain their catalogue number to be effective. */
    let removeBtn = document.getElementById(`reduce-${i.dataset.ctgnumber}`);
    
    let min = parseInt(i.min);
    let max = parseInt(i.max);

    // quantity modifiers
    addBtn.addEventListener("click", () => {
        // below maximum
        if (min <= parseInt(i.value) && parseInt(i.value) < max) {
            i.value++;
            i.dispatchEvent(new Event("input", { bubbles: true }));

        } else if (parseInt(i.value) < max) {
            // replicating the vanilla HTML input change
            i.value = min;
            i.dispatchEvent(new Event("input", { bubbles: true }));

        }
    });

    // accessibility
    addBtn.addEventListener("keydown", key => {
        if (key.key === "ArrowLeft" || key.key === "ArrowRight") {
            removeBtn.focus();
        }
    });

    removeBtn.addEventListener("click", () => {
        // above minimum
        if (max >= parseInt(i.value) && parseInt(i.value) > min) {
            i.value--;
            i.dispatchEvent(new Event("input", { bubbles: true }));

        } else if (parseInt(i.value) > max) {
            // replicating the vanilla HTML input change
            i.value = max;
            i.dispatchEvent(new Event("input", { bubbles: true }));
            
        }
    });

    // accessibility
    removeBtn.addEventListener("keydown", key => {
        if (key.key === "ArrowLeft" || key.key === "ArrowRight") {
            addBtn.focus();
        }
    });
}