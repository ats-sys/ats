var actionConfirmModalConfirmCallback = null;


/**
 * Hide AJAX loader
 * @param {*} time 
 */
function hideLoader(time){
    setTimeout(function(){
        $('#loader-container').hide();
    }, time ? time: 1000);
}

/**
 * Show AJAX loader
 */
function showLoader(){
    $('#loader-container').show();
}

function showSuccessFlash(message){
    $('.flash-msg-container').append(`
    <div class="alert alert-success alert-dismissible fade show" role="alert">
    <svg class="bi flex-shrink-0 me-2" width="24" height="24" role="img" aria-label="Success:"><use xlink:href="#check-circle-fill"/></svg>
        <div style="display: inline;">
            ${message}
        </div>
        <button type="button" class="btn-close float-end" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>`);
}

function showErrorFlash(message){
    $('.flash-msg-container').append(`
    <div class="alert alert-danger alert-dismissible fade show" role="alert">
        <svg class="bi flex-shrink-0 me-2" width="24" height="24" role="img" aria-label="Danger:"><use xlink:href="#exclamation-triangle-fill"/></svg>
        <div style="display: inline;">
            ${message}
        </div>
        <button type="button" class="btn-close float-end" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>`);
}

/**
 * Show action confirmation dialog box modal
 * @param {*} callback 
 */
function showActionConfirmDialog(title, message, callback){
    __setActionConfirmModalActionCallback(callback);

    $('#action-confirm-modal').find('.modal-title').html(title? title: 'Confirm Action');
    $('#action-confirm-modal').find('.modal-body').html(message? message: 'Are you sure you want to perform this action?');
    $('#action-confirm-modal').modal('show');
}

function showCommonInfoModal(title, message){
    $('#common-info-modal').find('.modal-title').html(title? title: '');
    $('#common-info-modal').find('.modal-body').html(message? message: '');
    $('#common-info-modal').modal('show');
}

function __setActionConfirmModalActionCallback(callback){
    actionConfirmModalConfirmCallback = function(){
        if(callback){
            callback();
        }
        actionConfirmModalConfirmCallback = null
    }
}

$(document).ready(function(){
    // When cancel button of the action confirmation dilog is clicked
    $('#action-confirm-modal-cancel').click(function(){
        $('#action-confirm-modal').modal('hide');
        actionConfirmModalConfirmCallback = null;
    });  
    
    $('#common-info-modal-cancel').click(function(){
        $('#common-info-modal').modal('hide');
    });    
    
    // When confirm button of the action confirmation dialog is clicked
    $('#action-confirm-modal-confirm').click(function(){
        $('#action-confirm-modal').modal('hide');
        
        if(actionConfirmModalConfirmCallback){
            actionConfirmModalConfirmCallback();
        }

        actionConfirmModalConfirmCallback = null;
    });
});