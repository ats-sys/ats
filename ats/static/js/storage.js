class Storage{
    constructor(){

    }

    async create(val){
        return new Promise((resolve, reject) => {
            $.ajax({
                    url: '/ajax/storage/create',
                    type: 'POST',
                    data: JSON.stringify(val),
                    headers: {"Content-Type": "application/json"},
                    success: function(response) {
                        resolve(response);
                    },
                    error: function(e){
                        reject(e)
                    }
                });
        });
    }

    async update(key, val){
        return new Promise((resolve, reject) => {
            $.ajax({
                    url: '/ajax/storage/update',
                    type: 'POST',
                    data: JSON.stringify({id: key, val: val}),
                    headers: {"Content-Type": "application/json"},
                    success: function(response) {
                        resolve(response);
                    },
                    error: function(e){
                        reject(e)
                    }
                });
        });
    }

    async get(key){
        return new Promise((resolve, reject) => {
            $.ajax({
                    url: '/ajax/storage/get',
                    type: 'POST',
                    data: JSON.stringify({id: key}),
                    headers: {"Content-Type": "application/json"},
                    success: function(response) {
                        resolve(response);
                    },
                    error: function(e){
                        reject(e)
                    }
                });
        });
    }

    async list(){
        return new Promise((resolve, reject) => {
            $.ajax({
                    url: '/ajax/storage/list',
                    type: 'POST',
                    data: JSON.stringify({}),
                    headers: {"Content-Type": "application/json"},
                    success: function(response) {
                        resolve(response);
                    },
                    error: function(e){
                        reject(e)
                    }
                });
        });
    }

    async remove(key){
        return new Promise((resolve, reject) => {
            $.ajax({
                    url: '/ajax/storage/delete',
                    type: 'POST',
                    data: JSON.stringify({id: key}),
                    headers: {"Content-Type": "application/json"},
                    success: function(response) {
                        resolve(response);
                    },
                    error: function(e){
                        reject(e)
                    }
                });
        });
    }
}