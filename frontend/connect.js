// ==================================================
// PROJECT OCTOPUS — CONNECTOR PAGE
// ==================================================

const connectorCards =
    document.querySelectorAll(".connector-card");

const selectedConnector =
    document.getElementById("selectedConnector");

const fileConfig =
    document.getElementById("fileConfig");

const mysqlConfig =
    document.getElementById("mysqlConfig");

const apiConfig =
    document.getElementById("apiConfig");

const sheetsConfig =
    document.getElementById("sheetsConfig");

const sourceFile =
    document.getElementById("sourceFile");

const connectButton =
    document.getElementById("connectButton");

const connectionMessage =
    document.getElementById("connectionMessage");


// ==================================================
// AUTHENTICATION / PERMISSION CHECK
// ==================================================

const loggedInUser =
    sessionStorage.getItem("octopusUser");

const permission =
    sessionStorage.getItem("octopusPermission");

if (!loggedInUser || permission !== "granted") {
    window.location.href = "/";
}


// ==================================================
// CURRENT CONNECTOR
// ==================================================

let selectedType = "excel";


// ==================================================
// CONNECTOR NAMES
// ==================================================

const connectorNames = {
    excel: "Excel Source",
    csv: "CSV Source",
    mysql: "MySQL Database",
    sheets: "Google Sheets",
    api: "API Source",
    file: "File Source"
};


// ==================================================
// SHOW CONFIGURATION
// ==================================================

function showConfiguration(type) {

    fileConfig.classList.add("hidden");
    mysqlConfig.classList.add("hidden");
    apiConfig.classList.add("hidden");
    sheetsConfig.classList.add("hidden");

    if (
        type === "excel" ||
        type === "csv" ||
        type === "file"
    ) {
        fileConfig.classList.remove("hidden");
    }

    if (type === "mysql") {
        mysqlConfig.classList.remove("hidden");
    }

    if (type === "api") {
        apiConfig.classList.remove("hidden");
    }

    if (type === "sheets") {
        sheetsConfig.classList.remove("hidden");
    }
}


// ==================================================
// SELECT CONNECTOR
// ==================================================

connectorCards.forEach(function (card) {

    card.addEventListener("click", function () {

        connectorCards.forEach(function (item) {
            item.classList.remove("active");
        });

        card.classList.add("active");

        selectedType =
            card.dataset.type;

        selectedConnector.textContent =
            connectorNames[selectedType];

        showConfiguration(
            selectedType
        );

        connectionMessage.textContent = "";

    });

});


// ==================================================
// INITIAL CONFIGURATION
// ==================================================

showConfiguration("excel");


// ==================================================
// CONNECT SOURCE
// ==================================================

connectButton.addEventListener(
    "click",
    async function () {

        connectionMessage.textContent =
            "Inspecting authorized source...";

        connectButton.disabled = true;


        try {

            // ==================================================
            // EXCEL / CSV / FILE
            // ==================================================

            if (
                selectedType === "excel" ||
                selectedType === "csv" ||
                selectedType === "file"
            ) {

                if (!sourceFile.files.length) {

                    connectionMessage.textContent =
                        "Please select an approved source file.";

                    connectButton.disabled = false;

                    return;
                }


                const file =
                    sourceFile.files[0];


                const fileName =
                    file.name.toLowerCase();


                const validFile =
                    fileName.endsWith(".xlsx") ||
                    fileName.endsWith(".xls") ||
                    fileName.endsWith(".csv");


                if (!validFile) {

                    connectionMessage.textContent =
                        "Please select a CSV or Excel file.";

                    connectButton.disabled = false;

                    return;
                }


                const formData =
                    new FormData();


                formData.append(
                    "file",
                    file
                );


                formData.append(
                    "connector_type",
                    selectedType
                );


                connectionMessage.textContent =
                    "Uploading and inspecting source...";


                const response =
                    await fetch(
                        "/api/connect/file",
                        {
                            method: "POST",
                            body: formData
                        }
                    );


                let result;

                try {

                    result =
                        await response.json();

                } catch (error) {

                    throw new Error(
                        "The server returned an invalid response."
                    );

                }


                if (!response.ok) {

                    throw new Error(
                        result.detail ||
                        result.message ||
                        "Source connection failed."
                    );

                }


                // Save backend result
                sessionStorage.setItem(
                    "octopusSource",
                    JSON.stringify(result)
                );


                // ==================================================
                // COMPLETE SUCCESS
                // ==================================================

                if (result.success === true) {

                    connectionMessage.textContent =
                        "Source processed successfully.";

                    sessionStorage.setItem(
                        "octopusIngestionResult",
                        JSON.stringify(result)
                    );

                    setTimeout(
                        function () {

                            window.location.href =
                                "/static/processing.html";

                        },
                        700
                    );

                    return;
                }


                // ==================================================
                // SCHEMA REVIEW REQUIRED
                // ==================================================

                const resultMessage =
                    String(
                        result.message || ""
                    ).toLowerCase();


                const requiresReview =
                    resultMessage.includes("schema mapping") ||
                    resultMessage.includes("administrator review") ||
                    resultMessage.includes("review required");


                if (requiresReview) {

                    connectionMessage.textContent =
                        "Schema detected. Opening administrator review...";


                    // Save the complete result
                    // for schema-review.html
                    sessionStorage.setItem(
                        "octopusSource",
                        JSON.stringify(result)
                    );


                    setTimeout(
                        function () {

                            window.location.href =
                                "/static/schema-review.html";

                        },
                        700
                    );


                    return;
                }


                // ==================================================
                // OTHER FAILURE
                // ==================================================

                connectionMessage.textContent =
                    result.message ||
                    "Unable to connect source.";

                connectButton.disabled = false;

                return;
            }


            // ==================================================
            // MYSQL
            // ==================================================

            if (selectedType === "mysql") {

                const host =
                    document.getElementById(
                        "dbHost"
                    ).value.trim();

                const port =
                    document.getElementById(
                        "dbPort"
                    ).value.trim();

                const database =
                    document.getElementById(
                        "dbName"
                    ).value.trim();

                const username =
                    document.getElementById(
                        "dbUser"
                    ).value.trim();

                const password =
                    document.getElementById(
                        "dbPassword"
                    ).value;


                if (
                    !host ||
                    !port ||
                    !database ||
                    !username ||
                    !password
                ) {

                    connectionMessage.textContent =
                        "Complete all MySQL connection fields.";

                    connectButton.disabled = false;

                    return;
                }


                connectionMessage.textContent =
                    "Sending authorized connection request...";


                const response =
                    await fetch(
                        "/api/connect/mysql",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                host: host,
                                port: port,
                                database: database,
                                username: username,
                                password: password

                            })
                        }
                    );


                let result;

                try {

                    result =
                        await response.json();

                } catch (error) {

                    throw new Error(
                        "The server returned an invalid response."
                    );

                }


                if (!response.ok) {

                    throw new Error(
                        result.detail ||
                        result.message ||
                        "MySQL connection failed."
                    );

                }


                connectionMessage.textContent =
                    result.message ||
                    "MySQL source inspected.";

                connectButton.disabled = false;

                return;
            }


            // ==================================================
            // API
            // ==================================================

            if (selectedType === "api") {

                const apiUrl =
                    document.getElementById(
                        "apiUrl"
                    ).value.trim();

                const apiAuth =
                    document.getElementById(
                        "apiAuth"
                    ).value;


                if (!apiUrl) {

                    connectionMessage.textContent =
                        "Enter the approved API endpoint.";

                    connectButton.disabled = false;

                    return;
                }


                connectionMessage.textContent =
                    "Preparing authorized API connection...";


                const response =
                    await fetch(
                        "/api/connect/api",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                url: apiUrl,

                                authentication:
                                    apiAuth

                            })
                        }
                    );


                let result;

                try {

                    result =
                        await response.json();

                } catch (error) {

                    throw new Error(
                        "The server returned an invalid response."
                    );

                }


                if (!response.ok) {

                    throw new Error(
                        result.detail ||
                        result.message ||
                        "API connection failed."
                    );

                }


                connectionMessage.textContent =
                    result.message ||
                    "API source inspected.";

                connectButton.disabled = false;

                return;
            }


            // ==================================================
            // GOOGLE SHEETS
            // ==================================================

            if (selectedType === "sheets") {

                const sheetReference =
                    document.getElementById(
                        "sheetReference"
                    ).value.trim();


                if (!sheetReference) {

                    connectionMessage.textContent =
                        "Enter the authorized Google Sheet reference.";

                    connectButton.disabled = false;

                    return;
                }


                connectionMessage.textContent =
                    "Preparing authorized Google Sheets connection...";


                const response =
                    await fetch(
                        "/api/connect/sheets",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                reference:
                                    sheetReference

                            })
                        }
                    );


                let result;

                try {

                    result =
                        await response.json();

                } catch (error) {

                    throw new Error(
                        "The server returned an invalid response."
                    );

                }


                if (!response.ok) {

                    throw new Error(
                        result.detail ||
                        result.message ||
                        "Google Sheets connection failed."
                    );

                }


                connectionMessage.textContent =
                    result.message ||
                    "Google Sheet inspected.";

                connectButton.disabled = false;

                return;
            }


            // ==================================================
            // UNKNOWN CONNECTOR
            // ==================================================

            connectionMessage.textContent =
                "Unsupported connector type.";

            connectButton.disabled = false;


        } catch (error) {

            console.error(
                "Project Octopus connector error:",
                error
            );


            connectionMessage.textContent =
                error.message ||
                "Unable to connect to the source.";

            connectButton.disabled = false;

        }

    }
);