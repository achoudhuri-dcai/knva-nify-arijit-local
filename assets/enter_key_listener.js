// This script listens for the Enter key press in a specific input field
// and triggers a button click when Enter is pressed.

const intervalId = setInterval(() => {
    var input = document.getElementById("human-chat-text-area");
    var button = document.getElementById("submit-button");
    console.log("Checking for input and button elements");
    if (input && button) {// are both the input and button not null
        console.log("Input and button elements found");
        // Add an event listener to the input field
        input.addEventListener("keypress", function(event) {
            // Check if the pressed key is "Enter"
            if (event.key === "Enter") {
                // Prevent the default action (form submission)
                // and trigger the button click
                event.preventDefault();
                button.click();
                console.log("Enter key pressed, button clicked. Input:", input.value);
            }
        });
        clearInterval(intervalId); // Stop checking once the elements are found and the listener is added
    }
}, 500);
// This will check every 500ms for the input and button elements
// and add the event listener once they are found
