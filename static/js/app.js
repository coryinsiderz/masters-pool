document.addEventListener("DOMContentLoaded", function () {
    // Hamburger menu toggle
    var toggle = document.querySelector(".nav-toggle");
    var links = document.querySelector(".nav-links");
    if (toggle && links) {
        toggle.addEventListener("click", function () {
            links.classList.toggle("open");
        });
    }

    // Custom dropdowns
    document.querySelectorAll(".custom-dropdown").forEach(function (dd) {
        var trigger = dd.querySelector(".custom-dropdown-trigger");
        var options = dd.querySelector(".custom-dropdown-options");
        var hidden = dd.querySelector("input[type=hidden]");
        var textSpan = trigger.querySelector(".dd-text");

        trigger.addEventListener("click", function (e) {
            e.stopPropagation();
            // Close all other dropdowns
            document.querySelectorAll(".custom-dropdown.open").forEach(function (other) {
                if (other !== dd) other.classList.remove("open");
            });
            dd.classList.toggle("open");
        });

        options.addEventListener("click", function (e) {
            var opt = e.target.closest(".custom-dropdown-option");
            if (!opt) return;
            var value = opt.getAttribute("data-value");
            var label = opt.textContent;
            hidden.value = value;
            textSpan.textContent = label;
            textSpan.classList.remove("dd-placeholder");
            // Update selected state
            options.querySelectorAll(".custom-dropdown-option").forEach(function (o) {
                o.classList.remove("selected");
            });
            opt.classList.add("selected");
            dd.classList.remove("open");
        });
    });

    // Close dropdowns when clicking outside
    document.addEventListener("click", function () {
        document.querySelectorAll(".custom-dropdown.open").forEach(function (dd) {
            dd.classList.remove("open");
        });
    });
});
