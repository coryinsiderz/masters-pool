document.addEventListener("DOMContentLoaded", function () {
    var dropdown = document.getElementById("their-team-dropdown");
    if (!dropdown) return;

    var myTab = document.getElementById("my-team-tab");
    var theirTab = document.getElementById("their-team-tab");
    var ddText = theirTab.querySelector(".dd-text");
    var optionsContainer = dropdown.querySelector(".custom-dropdown-options");
    var cardsContainer = document.querySelector(".squad-cards");
    var squadTotal = document.querySelector(".squad-total");
    var sbsToggleRow = document.getElementById("sbs-toggle-row");
    var sbsToggle = document.getElementById("sbs-toggle");
    var originalCardsHTML = cardsContainer ? cardsContainer.innerHTML : "";
    var originalTotal = squadTotal ? squadTotal.textContent : "";

    var myCards = null;
    var theirCards = null;
    var theirDisplayName = "";
    var theirTotal = "";
    var sbsActive = false;

    // Fetch current user's card data for SBS comparisons
    fetch("/api/team/" + CURRENT_USER_ID)
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.cards) myCards = data.cards;
        });

    // Fetch team summary and populate dropdown
    fetch("/api/teams/summary")
        .then(function (r) { return r.json(); })
        .then(function (users) {
            users.forEach(function (u) {
                if (u.user_id === CURRENT_USER_ID) return;
                var opt = document.createElement("div");
                opt.className = "custom-dropdown-option";
                opt.setAttribute("data-value", u.user_id);
                opt.textContent = u.display_name + "  (" + u.team_to_par + ")";
                optionsContainer.appendChild(opt);
            });
        });

    // Handle dropdown option selection
    optionsContainer.addEventListener("click", function (e) {
        var opt = e.target.closest(".custom-dropdown-option");
        if (!opt) return;
        var userId = opt.getAttribute("data-value");
        var label = opt.textContent;

        // Update active states
        myTab.classList.remove("active");
        theirTab.classList.add("active");
        ddText.textContent = label;

        // Mark selected option
        optionsContainer.querySelectorAll(".custom-dropdown-option").forEach(function (o) {
            o.classList.remove("selected");
        });
        opt.classList.add("selected");
        dropdown.classList.remove("open");

        // Show SBS toggle
        sbsToggleRow.style.display = "";

        // Fetch and render the selected user's team
        fetch("/api/team/" + userId)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                theirCards = data.cards;
                theirDisplayName = data.display_name;
                theirTotal = data.team_to_par;
                if (sbsActive && myCards) {
                    updateTotalForSbs();
                    renderSideBySide(myCards, theirCards);
                } else {
                    if (squadTotal) squadTotal.textContent = data.team_to_par;
                    renderCards(data.cards);
                }
            });
    });

    // Handle My Team tab click
    myTab.addEventListener("click", function () {
        myTab.classList.add("active");
        theirTab.classList.remove("active");
        ddText.textContent = "Their Team";
        optionsContainer.querySelectorAll(".custom-dropdown-option").forEach(function (o) {
            o.classList.remove("selected");
        });
        // Hide SBS toggle and reset state
        sbsToggleRow.style.display = "none";
        sbsToggle.classList.remove("active");
        sbsActive = false;
        theirCards = null;
        if (cardsContainer) cardsContainer.innerHTML = originalCardsHTML;
        if (squadTotal) squadTotal.textContent = originalTotal;
        bindOwnershipTriggers();
    });

    // Handle SBS toggle click
    sbsToggle.addEventListener("click", function () {
        if (!myCards || !theirCards) return;
        sbsActive = !sbsActive;
        if (sbsActive) {
            sbsToggle.classList.add("active");
            updateTotalForSbs();
            renderSideBySide(myCards, theirCards);
        } else {
            sbsToggle.classList.remove("active");
            if (squadTotal) squadTotal.textContent = theirTotal;
            renderCards(theirCards);
        }
    });

    function updateTotalForSbs() {
        if (squadTotal) {
            squadTotal.textContent = originalTotal + "  vs  " + theirDisplayName + " " + theirTotal;
        }
    }

    function renderSideBySide(mine, theirs) {
        if (!cardsContainer) return;
        var html = '<div class="sbs-container">';
        for (var i = 0; i < Math.max(mine.length, theirs.length); i++) {
            var myCard = mine[i] || {};
            var theirCard = theirs[i] || {};
            html += '<div class="sbs-row">';
            html += renderSbsCard(myCard);
            html += renderSbsCard(theirCard);
            html += '</div>';
        }
        html += '</div>';
        cardsContainer.innerHTML = html;
        bindOwnershipTriggers();
    }

    function renderSbsCard(c) {
        if (!c.name) return '<div class="sbs-card"></div>';
        var cls = "sbs-card" + (c.counting ? " counting" : "");
        var html = '<div class="' + cls + '">';
        html += '<div class="sc-tier">' + esc(c.tier_name) + '</div>';
        html += '<div class="sc-name">' + esc(c.name) + '</div>';
        html += '<div class="sc-score" style="color:var(--augusta-gold)">' + esc(c.to_par) + '</div>';
        html += '<div class="sc-details">';
        html += '<span class="sc-pos" style="color:var(--augusta-gold)">' + esc(c.position) + '</span>';
        html += '<span class="sc-own owned-trigger" data-golfer="' + esc(c.name) + '" data-owners="' + esc(c.owners) + '" data-pct="' + c.ownership_pct + '">' + c.ownership_pct + '%</span>';
        html += '</div></div>';
        return html;
    }

    function renderCards(cards) {
        if (!cardsContainer) return;
        var html = "";
        cards.forEach(function (c) {
            html += '<div class="squad-card' + (c.counting ? ' counting' : '') + '">';
            html += '<div class="sc-tier">' + esc(c.tier_name) + '</div>';
            html += '<div class="sc-main">';
            html += '<div class="sc-name">' + esc(c.name) + ' <span class="sc-own owned-trigger" data-owners="' + esc(c.owners) + '" data-golfer="' + esc(c.name) + '" data-pct="' + c.ownership_pct + '">' + c.ownership_pct + '%</span></div>';
            html += '<div class="sc-score" style="color:var(--augusta-gold)">' + esc(c.to_par) + '</div>';
            html += '</div>';
            html += '<div class="sc-details">';
            html += '<span class="sc-pos" style="color:var(--augusta-gold)">' + esc(c.position) + '</span>';
            html += '<span class="sc-thru">' + esc(c.thru) + '</span>';
            html += '</div>';
            html += '<div class="sc-rounds">';
            for (var r = 1; r <= 4; r++) {
                var roundScore = c["round_" + r];
                var cr = c.current_round;
                if (r === cr && c.thru && c.status === "active") {
                    html += '<span>R' + r + ': ' + esc(c.to_par) + ' ' + esc(c.thru) + '</span>';
                } else if (r < cr && roundScore) {
                    html += '<span>R' + r + ': ' + roundScore + '</span>';
                } else if (r === cr && !c.thru && roundScore) {
                    html += '<span>R' + r + ': ' + roundScore + '</span>';
                } else {
                    html += '<span>R' + r + ': --</span>';
                }
            }
            html += '</div></div>';
        });
        cardsContainer.innerHTML = html;
        bindOwnershipTriggers();
    }

    function bindOwnershipTriggers() {
        var overlay = document.getElementById("owner-modal-overlay");
        var modal = document.getElementById("owner-modal");
        if (!overlay || !modal) return;
        cardsContainer.querySelectorAll(".owned-trigger").forEach(function (trigger) {
            trigger.addEventListener("click", function (e) {
                e.stopPropagation();
                var owners = trigger.getAttribute("data-owners");
                var golfer = trigger.getAttribute("data-golfer") || "";
                var pct = trigger.getAttribute("data-pct") || "";
                if (!owners) return;
                var html = '<div class="owner-modal-title">' + golfer + '</div>';
                html += '<div class="owner-modal-pct">' + pct + '% owned</div>';
                owners.split(", ").forEach(function (name) {
                    html += '<div class="owner-modal-name">' + name + '</div>';
                });
                modal.innerHTML = html;
                overlay.classList.add("open");
            });
        });
    }

    function esc(str) {
        if (str === null || str === undefined) return "--";
        var d = document.createElement("div");
        d.textContent = String(str);
        return d.innerHTML;
    }
});
