const allowButton = document.getElementById("allowButton");
const denyButton = document.getElementById("denyButton");
const permissionMessage =
    document.getElementById("permissionMessage");


/*
==================================================
CHECK AUTHENTICATION
==================================================
*/

const loggedInUser =
    sessionStorage.getItem("octopusUser");

if (!loggedInUser) {

    window.location.href = "/";

}


/*
==================================================
ALLOW ACCESS
==================================================
*/

allowButton.addEventListener("click", function () {

    allowButton.disabled = true;
    denyButton.disabled = true;

    permissionMessage.textContent =
        "Access approved. Preparing secure connection...";

    sessionStorage.setItem(
        "octopusPermission",
        "granted"
    );

    setTimeout(function () {

        window.location.href =
            "/static/connect.html";

    }, 1000);

});


/*
==================================================
DENY ACCESS
==================================================
*/

denyButton.addEventListener("click", function () {

    sessionStorage.removeItem(
        "octopusPermission"
    );

    permissionMessage.textContent =
        "Access denied. Connection blocked.";

    allowButton.disabled = false;
    denyButton.disabled = false;

});