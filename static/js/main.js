
document.addEventListener("DOMContentLoaded", () => {

    /* =====================================
       1. FILE UPLOAD AND DRAG-AND-DROP
    ===================================== */

    const fileInput = document.getElementById("fileInput");
    const fileName = document.getElementById("fileName");
    const dropzone = document.getElementById("dropzone");

    if (fileInput && fileName) {
        fileInput.addEventListener("change", () => {
            fileName.textContent = fileInput.files.length
                ? fileInput.files[0].name
                : "";
        });
    }

    if (dropzone && fileInput) {

        ["dragenter", "dragover"].forEach(eventName => {
            dropzone.addEventListener(eventName, event => {
                event.preventDefault();
                dropzone.classList.add("dragover");
            });
        });

        ["dragleave", "drop"].forEach(eventName => {
            dropzone.addEventListener(eventName, event => {
                event.preventDefault();
                dropzone.classList.remove("dragover");
            });
        });

        dropzone.addEventListener("drop", event => {
            const files = event.dataTransfer.files;

            if (files.length > 0) {
                fileInput.files = files;

                if (fileName) {
                    fileName.textContent = files[0].name;
                }
            }
        });
    }


    /* =====================================
       2. AUTO-DISMISS ALERT MESSAGES
    ===================================== */

    document.querySelectorAll(".alert").forEach(alert => {

        setTimeout(() => {
            alert.style.transition = "opacity 0.3s ease";
            alert.style.opacity = "0";

            setTimeout(() => {
                alert.style.display = "none";
            }, 300);

        }, 5000);

    });


    /* =====================================
       3. GRANT ACCESS PANEL
       OPEN AND CLOSE
    ===================================== */

    function getGrantAccessPanel() {
        return (
            document.getElementById("sharePanel") ||
            document.getElementById("grantAccessPanel")
        );
    }

    function getGrantAccessOverlay() {
        return (
            document.getElementById("shareOverlay") ||
            document.getElementById("grantAccessOverlay")
        );
    }


    // Close a sliding Grant Access panel, if your page uses one.
    function closeGrantAccessPanel() {

        const panel = getGrantAccessPanel();
        const overlay = getGrantAccessOverlay();

        if (panel) {
            panel.classList.remove("open");
            panel.setAttribute("aria-hidden", "true");
            panel.style.transform = "translateX(100%)";
            panel.style.visibility = "hidden";
            panel.style.pointerEvents = "none";
        }

        if (overlay) {
            overlay.classList.remove("open");
            overlay.setAttribute("aria-hidden", "true");
            overlay.style.opacity = "0";
            overlay.style.visibility = "hidden";
            overlay.style.pointerEvents = "none";
        }

        document.body.style.overflow = "";
    }


    // Open a sliding Grant Access panel, if your page uses one.
    function openGrantAccessPanel() {

        const panel = getGrantAccessPanel();
        const overlay = getGrantAccessOverlay();

        if (panel) {
            panel.classList.add("open");
            panel.setAttribute("aria-hidden", "false");
            panel.style.transform = "translateX(0)";
            panel.style.visibility = "visible";
            panel.style.pointerEvents = "auto";
        }

        if (overlay) {
            overlay.classList.add("open");
            overlay.setAttribute("aria-hidden", "false");
            overlay.style.opacity = "1";
            overlay.style.visibility = "visible";
            overlay.style.pointerEvents = "auto";
        }

        if (panel || overlay) {
            document.body.style.overflow = "hidden";
        }
    }


    /* =====================================
       4. CLOSE THE CORRECT DOCUMENT POPOVER
    ===================================== */

    // Event delegation supports multiple document menus.
    document.addEventListener("click", event => {

        const closeButton = event.target.closest(
            ".close-access-btn, " +
            "#closeGrantAccessBtn, " +
            "[data-close-grant-access]"
        );

        if (closeButton) {
            event.preventDefault();
            event.stopPropagation();

            // IMPORTANT:
            // Your document menu uses:
            // <details class="share-menu">
            // Close that specific menu first.
            const shareMenu = closeButton.closest(".share-menu");

            if (shareMenu) {
                shareMenu.open = false;
                return;
            }

            // Otherwise, close the sliding panel.
            closeGrantAccessPanel();
            return;
        }


        // Close the sliding panel when its overlay is clicked.
        const overlay = getGrantAccessOverlay();

        if (overlay && event.target === overlay) {
            closeGrantAccessPanel();
            return;
        }


        // Open a sliding panel when an opener is clicked.
        const openButton = event.target.closest(
            "[data-open-grant-access]"
        );

        if (openButton) {
            event.preventDefault();
            openGrantAccessPanel();
        }

    });


    // Close open menus or the sliding panel with Escape.
    document.addEventListener("keydown", event => {

        if (event.key !== "Escape") {
            return;
        }

        document.querySelectorAll(
            ".share-menu[open]"
        ).forEach(menu => {
            menu.open = false;
        });

        closeGrantAccessPanel();
    });


    /* =====================================
       5. SEARCH AND SELECT COMPANY USERS
    ===================================== */

    const searchInputs = document.querySelectorAll(
        "[data-share-user-search]"
    );

    searchInputs.forEach(searchInput => {

        const resultsId = searchInput.dataset.resultsId;
        const hiddenId = searchInput.dataset.hiddenId;

        const results = resultsId
            ? document.getElementById(resultsId)
            : null;

        const hiddenInput = hiddenId
            ? document.getElementById(hiddenId)
            : null;

        const form = searchInput.closest("form");

        if (!results || !hiddenInput || !form) {
            console.warn(
                "Share-user search is missing its results, hidden input, or form.",
                searchInput
            );
            return;
        }

        const selectionNote = form.querySelector(
            "[data-share-user-selection]"
        );

        const options = Array.from(
            results.querySelectorAll(".share-user-option")
        );


        // Search users by name or email.
        searchInput.addEventListener("input", () => {

            const query = searchInput.value.trim().toLowerCase();

            // Reset the previous selection.
            hiddenInput.value = "";

            if (selectionNote) {
                selectionNote.textContent = "No user selected.";
            }

            let matches = 0;

            options.forEach(option => {

                const searchText = (
                    option.dataset.search || ""
                ).toLowerCase();

                const matched =
                    query.length > 0 &&
                    searchText.includes(query);

                option.hidden = !matched;

                if (matched) {
                    matches++;
                }
            });

            results.hidden =
                query.length === 0 || matches === 0;

            searchInput.setCustomValidity("");
        });


        // Select a user from the search results.
        results.addEventListener("click", event => {

            const option = event.target.closest(
                ".share-user-option"
            );

            if (!option || option.hidden) {
                return;
            }

            hiddenInput.value = option.dataset.userId || "";

            searchInput.value =
                option.dataset.userLabel || "";

            results.hidden = true;

            if (selectionNote) {
                selectionNote.textContent =
                    "Selected: " + searchInput.value;
            }

            searchInput.setCustomValidity("");
        });


        // Require the user to select a result before submitting.
        form.addEventListener("submit", event => {

            if (!hiddenInput.value) {

                event.preventDefault();

                searchInput.setCustomValidity(
                    "Search for a user and select a result."
                );

                searchInput.reportValidity();
                searchInput.focus();
            }
        });

    });


    /* =====================================
       6. CLOSE SEARCH RESULTS WHEN CLICKING OUTSIDE
    ===================================== */

    document.addEventListener("click", event => {

        document.querySelectorAll(
            "[data-share-user-search]"
        ).forEach(searchInput => {

            const resultsId = searchInput.dataset.resultsId;

            const results = resultsId
                ? document.getElementById(resultsId)
                : null;

            if (!results) {
                return;
            }

            if (
                !searchInput.contains(event.target) &&
                !results.contains(event.target)
            ) {
                results.hidden = true;
            }
        });

    });

});