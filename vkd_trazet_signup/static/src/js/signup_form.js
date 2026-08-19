(function () {
    "use strict";

    function initCombobox(root) {
        var input = root.querySelector(".trazet-combobox-input");
        var hidden = root.querySelector(".trazet-combobox-value");
        var menu = root.querySelector(".trazet-combobox-menu");
        var options = Array.prototype.slice.call(menu.querySelectorAll(".trazet-combobox-option"));

        function showMenu() {
            menu.classList.add("trazet-combobox-menu-open");
        }
        function hideMenu() {
            menu.classList.remove("trazet-combobox-menu-open");
        }
        function filter() {
            var term = input.value.trim().toLowerCase();
            var anyVisible = false;
            options.forEach(function (opt) {
                var match = !term || opt.textContent.toLowerCase().indexOf(term) !== -1;
                opt.style.display = match ? "" : "none";
                anyVisible = anyVisible || match;
            });
            menu.classList.toggle("trazet-combobox-empty", !anyVisible);
        }

        input.addEventListener("focus", function () {
            filter();
            showMenu();
        });
        input.addEventListener("input", function () {
            hidden.value = "";
            input.classList.remove("is-invalid");
            filter();
            showMenu();
        });
        input.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape") {
                hideMenu();
            }
        });
        options.forEach(function (opt) {
            opt.addEventListener("mousedown", function (ev) {
                ev.preventDefault();
                hidden.value = opt.getAttribute("data-value");
                input.value = opt.textContent.trim();
                input.classList.remove("is-invalid");
                hideMenu();
            });
        });
        document.addEventListener("click", function (ev) {
            if (!root.contains(ev.target)) {
                hideMenu();
            }
        });
    }

    function initEmailLowercase(form) {
        var email = form.querySelector('input[type="email"]');
        if (!email) {
            return;
        }
        email.addEventListener("input", function () {
            var pos = email.selectionStart;
            email.value = email.value.toLowerCase();
            if (pos !== null && email.setSelectionRange) {
                email.setSelectionRange(pos, pos);
            }
        });
    }

    function initComboboxValidation(form) {
        form.addEventListener("submit", function (ev) {
            var invalid = Array.prototype.slice.call(
                form.querySelectorAll('.trazet-combobox[data-required="true"]')
            ).filter(function (root) {
                return !root.querySelector(".trazet-combobox-value").value;
            });
            if (invalid.length) {
                ev.preventDefault();
                invalid.forEach(function (root) {
                    root.querySelector(".trazet-combobox-input").classList.add("is-invalid");
                });
                invalid[0].querySelector(".trazet-combobox-input").focus();
            }
        });
    }

    function initSignupForm() {
        var form = document.getElementById("trazet_signup_form");
        if (!form) {
            return;
        }
        form.querySelectorAll(".trazet-combobox").forEach(initCombobox);
        initEmailLowercase(form);
        initComboboxValidation(form);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initSignupForm);
    } else {
        initSignupForm();
    }
})();