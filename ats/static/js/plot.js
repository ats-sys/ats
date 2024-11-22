$(document).ready(async function(){
    var jobConfig = await getData(job_id);

    console.log(jobConfig && jobConfig.plots[plot_id])

    if(jobConfig && jobConfig.plots[plot_id])
    {
        if(jobConfig.plots[plot_id].name)
            delete jobConfig.plots[plot_id].name;

        $.ajax({
        url: '/trading_job/plot_topics/' + jobConfig.trading_job_id,
        type: 'POST',
        data: JSON.stringify(jobConfig.plots[plot_id]),
        headers: {"Content-Type": "application/json"},
        success: function(response) {
            populateIframe(response)

        }
    });
    }
    
});

function populateIframe(htmlContent) {
    console.log(htmlContent);
    $("#plot-content").contents().find('body').html(htmlContent);
    hideLoader();
  }

// Converts a timestamp to a DD-MM-YYYY HH:MM format
function formatTimestamp(timestamp){
    const utcTimestamp = timestamp; // Replace this with your UTC timestamp

    // Create a new Date object using the UTC timestamp
    const date = new Date(utcTimestamp);

    // Get individual date components in the local timezone
    const day = ('0' + date.getDate()).slice(-2);
    const month = ('0' + (date.getMonth() + 1)).slice(-2);
    const year = date.getFullYear();
    const hours = ('0' + date.getHours()).slice(-2);
    const minutes = ('0' + date.getMinutes()).slice(-2);

    // Construct the formatted date string (DD-MM-YYYY HH:MM)
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}

// CRUD operations for data using local storage

function saveData(token, data) {
    if (!token || !data) {
      throw new Error("Token and data are required arguments.");
    }
    try {
      // Choose a storage mechanism (localStorage or sessionStorage)
      const storage = localStorage; // Change to sessionStorage if needed
  
      // Stringify the data object before storing
      const jsonData = JSON.stringify(data);
      storage.setItem(token, jsonData);
    } catch (error) {
      console.error("Error saving data:", error);
    }
}

async function getData(token) {
    if (!token) {
      throw new Error("Token is a required argument.");
    }
    try {
      const storage = new Storage();
      const jsonData = await storage.get(token);
  
      // Parse the JSON string back into a JS object
      return jsonData || null;
    } catch (error) {
      console.error("Error retrieving data:", error);
      return null;
    }
  }

  function modifyData(token, newData) {
    if (!token || !newData) {
      throw new Error("Token and new data are required arguments.");
    }
    const existingData = getData(token);
    if (existingData === null) {
      console.warn("No data found for the provided token:", token);
      return;
    }
  
    const mergedData = {...existingData, ...newData};
    saveData(token, mergedData);
}
  
function deleteData(token) {
    if (!token) {
        throw new Error("Token is a required argument.");
    }
    try {
        const storage = localStorage; // Change to sessionStorage if needed
        storage.removeItem(token);
    } catch (error) {
        console.error("Error deleting data:", error);
    }
}

function listData(){
    try{
        const records = [];
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          const value = JSON.parse(localStorage.getItem(key));
          records.push(value); // Use key as the "token" identifier
        }
        return records;
    } catch(error){
        console.error('Error listing data')
    }
}

