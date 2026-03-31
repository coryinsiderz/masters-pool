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

    // ── Sortable table ──
    var table = document.getElementById("leaderboard");
    if (table) {
        var thead = table.querySelector("thead");
        var tbody = table.querySelector("tbody");
        var headers = thead.querySelectorAll("th[data-sort]");
        var currentSort = null;
        var ascending = true;

        headers.forEach(function (th) {
            th.style.cursor = "pointer";
            th.addEventListener("click", function (e) {
                e.stopPropagation();
                var key = th.getAttribute("data-sort");
                if (currentSort === key) {
                    ascending = !ascending;
                } else {
                    currentSort = key;
                    ascending = true;
                }
                headers.forEach(function (h) {
                    h.classList.remove("sort-asc", "sort-desc");
                });
                th.classList.add(ascending ? "sort-asc" : "sort-desc");
                sortTable(key, ascending);
            });
        });

        function parseToPar(val) {
            if (!val || val === "--" || val === "E") return 0;
            var n = parseInt(val, 10);
            return isNaN(n) ? 9999 : n;
        }

        function sortTable(key, asc) {
            var rows = Array.from(tbody.querySelectorAll("tr"));
            rows.sort(function (a, b) {
                var va, vb;
                if (key === "name") {
                    va = a.getAttribute("data-name") || "";
                    vb = b.getAttribute("data-name") || "";
                    return asc ? va.localeCompare(vb) : vb.localeCompare(va);
                } else if (key === "total") {
                    va = parseToPar(a.getAttribute("data-total"));
                    vb = parseToPar(b.getAttribute("data-total"));
                } else if (key.startsWith("tier-")) {
                    var tier = key.split("-")[1];
                    va = parseToPar(a.getAttribute("data-tier-" + tier + "-par"));
                    vb = parseToPar(b.getAttribute("data-tier-" + tier + "-par"));
                } else {
                    return 0;
                }
                if (va === vb) return 0;
                return asc ? va - vb : vb - va;
            });
            rows.forEach(function (row) {
                tbody.appendChild(row);
            });
        }
    }

    // ── Expandable leaderboard rows ──
    var expandableRows = document.querySelectorAll(".expandable-row");
    expandableRows.forEach(function (row) {
        row.addEventListener("click", function (e) {
            if (e.target.closest(".owned-trigger")) return;
            e.stopPropagation();
            var detailRow = row.nextElementSibling;
            if (!detailRow || !detailRow.classList.contains("detail-row")) return;
            var isOpen = row.classList.contains("expanded");
            expandableRows.forEach(function (r) {
                r.classList.remove("expanded");
                var dr = r.nextElementSibling;
                if (dr && dr.classList.contains("detail-row")) {
                    dr.style.display = "none";
                }
            });
            if (!isOpen) {
                row.classList.add("expanded");
                detailRow.style.display = "";
            }
        });
    });

    // ── Scores filter toggle ──
    var filterBtn = document.getElementById("scores-filter");
    if (filterBtn) {
        var filtered = false;
        filterBtn.addEventListener("click", function () {
            var table = document.getElementById("scores-table");
            if (!table) return;
            filtered = !filtered;
            var rows = table.querySelectorAll("tbody tr");
            rows.forEach(function (row) {
                if (filtered && !row.classList.contains("my-player")) {
                    row.style.display = "none";
                } else {
                    row.style.display = "";
                }
            });
            filterBtn.textContent = filtered ? "All Players" : "My Players";
        });
    }

    // ── Ownership modal ──
    var overlay = document.getElementById("owner-modal-overlay");
    var modal = document.getElementById("owner-modal");

    if (overlay) {
        overlay.addEventListener("click", function (e) {
            if (e.target === overlay) {
                overlay.classList.remove("open");
            }
        });
    }

    document.querySelectorAll(".owned-trigger").forEach(function (trigger) {
        trigger.addEventListener("click", function (e) {
            e.stopPropagation();
            if (!overlay || !modal) return;
            var owners = trigger.getAttribute("data-owners");
            var golfer = trigger.getAttribute("data-golfer") || "";
            var pct = trigger.getAttribute("data-pct") || "";
            if (!owners) return;

            var html = '<div class="owner-modal-title">' + golfer + '</div>';
            html += '<div class="owner-modal-pct">' + pct + '% owned</div>';
            var names = owners.split(", ");
            names.forEach(function (name) {
                html += '<div class="owner-modal-name">' + name + '</div>';
            });
            modal.innerHTML = html;
            overlay.classList.add("open");
        });
    });
});
