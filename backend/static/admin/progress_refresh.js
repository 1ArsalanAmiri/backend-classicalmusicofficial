setInterval(function(){

    fetch(window.location.href)
    .then(response => response.text())
    .then(html => {

        let parser = new DOMParser();
        let doc = parser.parseFromString(html, "text/html");

        let newTable = doc.querySelector("#result_list");

        if(newTable){
            document.querySelector("#result_list").innerHTML = newTable.innerHTML;
        }

    });

}, 3000);
