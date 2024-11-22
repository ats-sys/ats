var jobConfig
var plotConfig
var dataTable
var runningTradingJobs = {} // map between, UI job id and trader job id

const storage = new Storage(); // Change to sessionStorage if needed

$(document).ready(async function(){
    getList(function(data){
        reloadTable(data);
        hideLoader();
    });

    setInterval(function(){
        updateProgressInList()
    },1000)

    jobConfig = new JSONEditor($('#json-editor-job-config')[0], {mode: 'code', mainMenuBar: false});
    plotConfig = new JSONEditor($('#json-editor-plot-config')[0], {mode: 'code', mainMenuBar: false});

    $('#btn-open-create-job-modal').click(function(){openJobModal(null, 'CREATE')});
    $('#btn-save-job').click(function(){
        // hideJobModal()
        if($('#add-job-modal').data('mode') == 'CREATE'){
            createConfigRecord(async function(id){
                getList(reloadTable);
            });
        }
        else{
            editConfigRecord($('#add-job-modal').data('id'), async function(id){
                getList(reloadTable);
            });
        }
    });
});

function openModalFromRecord(id){
    find(id, function(data){openJobModal(data, 'EDIT')})
}

function openJobModal(data, createOrEdit){
    var initialJSON = {};

    //    Fill the form
    setModalData(data);

    if(createOrEdit == 'CREATE'){
        $('#config-modal-title').html('Create Config')
        $('#add-job-modal').data('mode', 'CREATE');
        $('#add-job-modal').data('id', '');
    }

    if(createOrEdit == 'EDIT'){
        $('#config-modal-title').html('Edit Config');
        $('#add-job-modal').data('mode', 'EDIT');
        $('#add-job-modal').data('id', data.id);
    }
    $('#add-job-modal').modal('show')
}


// Hide the job config modal
function hideJobModal(){
    $('#add-job-modal').modal('hide')
}

// Set job config modal data
function setModalData(data){
    if(data){
        $('#modal-config-name').val(data.name)
        jobConfig.set(data.config);
        plotConfig.set(data.plots);
    }
    else{
        $('#modal-config-name').val('')
        jobConfig.set({});
        plotConfig.set([]);
    }
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

async function createConfigRecord(callback){
//    var id = crypto.randomUUID()
    var data = {
//        id: id,
        trading_job_id: null,
        createdTime: new Date().getTime(),
        name: $('#modal-config-name').val(),
        config: jobConfig.get(),
        plots: plotConfig.get(),
        state: "STOPPED"
    };

    if(!Array.isArray(data.plots)){
        showErrorFlash(`Plots must be an array. Given ${typeof data.plots}`);
        hideJobModal();
        hideLoader();
        return;
    }

    showLoader();

    var id = await storage.create(data);
    data.id = id;

    await storage.update(id, data);

    if(callback){
        callback(id);
    }

    hideLoader();
    hideJobModal();
    showSuccessFlash(`Job id ${data.id} is saved.`)
    
}

function editConfigRecord(id, callback){
    var data = {
            id: id,
            name: $('#modal-config-name').val(),
            config: jobConfig.get(),
            plots: plotConfig.get()
        }
    
    showLoader();

    if(!Array.isArray(data.plots)){
        showErrorFlash(`Plots must be an array. Given ${typeof data.plots}`);
        hideJobModal();
        hideLoader();
        return;
    }

    modifyData(id, data);

    if(callback){
        callback(id);
    }

    hideLoader();
    hideJobModal();
    showSuccessFlash(`Job id ${data.id} is saved.`)
}

function deleteRecord(id){
    showActionConfirmDialog(null, 'Are you sure you want to delete this job?', async function(){
        showLoader();
        deleteData(id);
        getList(function(data){reloadTable(data)});
        hideLoader();
        showSuccessFlash(`Job id ${id} is deleted.`)
    });
}

async function runJob(id){
    showActionConfirmDialog(null, 'Are you sure you want to run this job?', async function(){
        showLoader();
        var jobConfig = await getData(id)
        createTradingJob(jobConfig.config,function(response){
            jobConfig.trading_job_id = response.job_id
            saveData(id, jobConfig);
            runTradingJob(response.job_id, function(){
                console.log('Running for job id: ', response.job_id)
                hideLoader();
            })
        })
    });
}

async function stopJob(id){
    showActionConfirmDialog(null, 'Are you sure you want to stop this job?', async function(){
        showLoader();
        var jobConfig = await getData(id)
        stopTradingJob(jobConfig.trading_job_id, function(){
            hideLoader();
        })
    });
}

// Get the find is from AJAX
async function find(id, callback){
    showLoader();
    data = await getData(id);
    if(callback){
        callback(data);
    }
    hideLoader();
}

// Get the list from AJAX
function getList(callback){
    listData().then((dataList)=>{
        if(callback)
            callback(dataList);
    });
}

// Reload the table with data
function reloadTable(records){
    var formattedRecords = []

    if(records.length){
        $('#list-wrapper').show();
        $('#no-trading-jobs-msg').hide();
    }else{
        $('#list-wrapper').hide();
        $('#no-trading-jobs-msg').show();
    }

    records.forEach(function(record){
        var badgeName = record.state == 'RUNNING'? 'bg-success':
            (record.state == 'STOPPED' ? 'bg-dark':
                (record.state == 'TERMINATED'? 'bg-danger': 'bg-secondary'))
        var badge = `<h6><span data-job_id="${record.id}" data-job_state="${record.state}" class="badge job-state ${badgeName}">${record.state}</span></h6>`

        var newRecord = [
            formatTimestamp(record.createdTime),
            record.name,
            badge,
            `<button class="btn btn-sm btn-light record-edit-btn" onclick="openModalFromRecord('${record.id}')"><i class="bi bi-pencil-square"></i></button> 
                &nbsp;
            <button class="btn btn-run btn-sm ${record.state !== 'RUNNING'? 'btn-success' : 'btn-danger'} record-state-btn" onclick="__runOrStopBasedOnState('${record.id}')">${record.state !== 'RUNNING'? '<i class="bi bi-play-circle-fill"></i>' : '<i class="bi bi-stop-circle-fill"></i>'}</button>
                &nbsp;
            <button class="btn btn-light btn-plot btn-sm" onclick="__plotOptionShowModal('${record.id}')"><i class="bi bi-graph-up"></i></button>
                &nbsp;
            <button class="btn btn-sm btn-danger record-edit-btn" onclick="deleteRecord('${record.id}')"><i class="bi bi-trash-fill"></i></button>`
        ];
        formattedRecords.push(newRecord);
    });

    if(!dataTable){
        dataTable = new gridjs.Grid({
          columns: [
            {
                name: "Date",
                width: '200px' ,
                sort: {
                    compare: (a, b) => {
                      if (a > b) {
                        return 0;
                      } else if (b > a) {
                        return -1;
                      } else {
                        return 1;
                      }
                    }
                  }
            },
            {
                name: 'Name',
                width: '350px'
            },
            {
                name: 'State',
                width: '150px' ,
                formatter: (_, row) => gridjs.html(row.cells[2].data)
            },
            {
                name: 'Actions',
                formatter: (_, row) => gridjs.html(row.cells[3].data)
            }
          ],
          data: formattedRecords,
          sort: true,
          pagination: {
            limit: 5
          }
        }).render($("#list-wrapper")[0]);
    } else{
        dataTable.updateConfig({
            data: formattedRecords
        }).forceRender();
    }
}

function updateProgressInList(){
    var indexedResults = {}

    getTradingJobList(function(response){
        response.forEach(function(item, idx){
            indexedResults[item.id] = item;
        });

        $('.job-state').each(async function(idx, ele){
            if($(ele).data('job_id')){
                var tradingJob = await getData($(ele).data('job_id'));

                // Button icon and color change depending on the job state
                $(ele).parents('tr').find('.btn-run').html(tradingJob.state !== 'RUNNING'? '<i class="bi bi-play-circle-fill"></i>' : '<i class="bi bi-stop-circle-fill"></i>')
                if(tradingJob.state !== 'RUNNING'){
                    $(ele).parents('tr').find('.btn-run').addClass('btn-success');
                    $(ele).parents('tr').find('.btn-run').removeClass('btn-danger');
                }
                else{
                    $(ele).parents('tr').find('.btn-run').addClass('btn-danger');
                    $(ele).parents('tr').find('.btn-run').removeClass('btn-success');
                }

                if(tradingJob && tradingJob.trading_job_id && indexedResults[tradingJob.trading_job_id]){
                    var tradingJobStatus = indexedResults[tradingJob.trading_job_id];

                    if(tradingJobStatus.is_running){
                        tradingJob.state = 'RUNNING';
                        saveData($(ele).data('job_id'), tradingJob);

                        if(tradingJobStatus.exchange.back_trading_progress){
                            $(ele).html( 'PROGESS: ' + parseFloat( tradingJobStatus.exchange.back_trading_progress.toPrecision(3)) + '%');
                            $(ele).removeClass('bg-dark');
                            $(ele).addClass('bg-success');
                        }
                        else{
                            $(ele).html('RUNNING')
                            $(ele).removeClass('bg-dark');
                            $(ele).addClass('bg-success');
                        }
                    }
                    else{
                        $(ele).html('STOPPED');
                        $(ele).addClass('bg-dark');
                        $(ele).removeClass('bg-success');

                        tradingJob.state = 'STOPPED';
                        saveData($(ele).data('job_id'), tradingJob);
                    }
                }
                else if(tradingJob && !indexedResults[tradingJob.trading_job_id]){
                    tradingJob.state = 'STOPPED';
                    saveData($(ele).data('job_id'), tradingJob);
                }
                
            }
        });
    })
}

// CRUD operations for data using local storage

function saveData(token, data) {
    if (!token || !data) {
      throw new Error("Token and data are required arguments.");
    }
    try {
      // Choose a storage mechanism (localStorage or sessionStorage)
      // Stringify the data object before storing
//      const jsonData = JSON.stringify(data);
      storage.update(token, data);
    } catch (error) {
      console.error("Error saving data:", error);
    }
}

async function getData(token) {
    if (!token) {
      throw new Error("Token is a required argument.");
    }
    try {
//      const storage = localStorage; // Change to sessionStorage if needed
      return await storage.get(token);
    } catch (error) {
      console.error("Error retrieving data:", error);
      return null;
    }
  }

  async function modifyData(token, newData) {
    console.log([token, newData])

    if (!token || !newData) {
      throw new Error("Token and new data are required arguments.");
    }
    const existingData = await getData(token);
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
//        const storage = localStorage; // Change to sessionStorage if needed
        storage.remove(token);
    } catch (error) {
        console.error("Error deleting data:", error);
    }
}

function deleteData(token) {
    if (!token) {
        throw new Error("Token is a required argument.");
    }
    try {
//        const storage = localStorage; // Change to sessionStorage if needed
        storage.remove(token);
    } catch (error) {
        console.error("Error deleting data:", error);
    }
}

async function listData(){
    console.log('>>>>>>>>>>> ');
    try{
        const listItems =  await storage.list();
        const records = [];
        for (let i = 0; i < listItems.length; i++) {
//          const key = localStorage.key(i);
//          const value = JSON.parse(localStorage.getItem(key));
          records.push(listItems[i]); // Use key as the "token" identifier
        }
        console.log(records);
        return records;
    } catch(error){
        console.error('Error listing data');
        throw error;
    }
}

// Calling trader APIs

function createTradingJob(data, callback){
    $.ajax({
        url: '/trading_job/create',
        type: 'POST',
        data: JSON.stringify(data),
        headers: {"Content-Type": "application/json"},
        success: function(response) {
            if(!response.job_id){
                showErrorFlash('Error occured while creating a trading job in Trader.')
            }
            else{
                if(callback){
                    callback(response);
                }
            }
        }
    });
}

function runTradingJob(id, callback){
    $.ajax({
        url:  '/trading_job/run/' + id,
        type: 'GET',
        success: function(response) {
            if(!response.job_id){
                showErrorFlash('Error occured while trying to rung the trading job.')
            }
            else{
                if(callback){
                    callback()
                }
                showSuccessFlash("Trading job started.");
            }
        }
    });
}

function stopTradingJob(id, callback){
    $.ajax({
        url:  '/trading_job/stop/' + id,
        type: 'GET',
        success: function(response) {
            if(!response.job_id){
                showErrorFlash('Error occured while trying to rung the stopping job.')
            }
            else{
                if(callback){
                    callback()
                }
                showSuccessFlash("Trading job stopped.");
            }
        }
    });
}

function getTradingJobList(callback){
    $.ajax({
        url:  '/trading_job/list',
        type: 'GET',
        success: function(response) {
            if(!Array.isArray(response)){
                showErrorFlash('Error occurred while fetching status.')
            }
            else{
                if(callback){
                    callback(response)
                }
            }
        }
    });
}

async function __runOrStopBasedOnState(id){
    var jobConfig = await getData(id);
    console.log(jobConfig)
    if(jobConfig.state == 'STOPPED'){
        runJob(id);
    }
    else{
        stopJob(id);
    }
}

async function __plotOptionShowModal(id){
    var jobConfig = await getData(id);
    console.log(jobConfig)

    var modalBody = 'No plots are configured...'

    if(jobConfig && jobConfig.plots && jobConfig.plots.length){
        modalBody = 'Please select the plot you want to see.<br/><br/>';

        jobConfig.plots.forEach(function(plotConfig, idx){
            modalBody += `<a href="/portal/strategy_tester/plot/${jobConfig.id}/${idx}" target="_blank">${plotConfig.name? plotConfig.name : 'Plot ' + (idx + 1)}</a> &nbsp; &nbsp; &nbsp;`
        })

    }

    showCommonInfoModal('Plots',modalBody)
}
