function checkFormCompletion() {
    var form = document.getElementById('review-form');
    var radioGroups = form.querySelectorAll('input[type="radio"]');
    var submitButton = document.getElementById('submit-button');

    var allSelected = true;
    var groups = {};
    radioGroups.forEach(function(radio) {
        var name = radio.name;
        if (!groups[name]) {
            groups[name] = false;
        }
        if (radio.checked) {
            groups[name] = true;
        }
    });

    for (var key in groups) {
        if (!groups[key]) {
            allSelected = false;
            break;
        }
    }

    submitButton.disabled = !(allSelected && cropCompleted);
}
