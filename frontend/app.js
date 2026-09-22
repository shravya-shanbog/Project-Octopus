const loginForm = document.getElementById("loginForm");
const loginMessage = document.getElementById("loginMessage");

loginForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    loginMessage.textContent = "Authenticating...";

    try {

        const response = await fetch("/api/login", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                email: email,
                password: password
            })

        });

        const result = await response.json();

        if (result.success) {

            loginMessage.textContent =
                "Authentication successful.";

            sessionStorage.setItem(
                "octopusUser",
                JSON.stringify(result.user)
            );

            setTimeout(function () {

                window.location.href =
                    "/static/permission.html";

            }, 700);

        } else {

            loginMessage.textContent =
                result.message;

        }

    } catch (error) {

        console.error(error);

        loginMessage.textContent =
            "Unable to connect to authentication service.";

    }

});