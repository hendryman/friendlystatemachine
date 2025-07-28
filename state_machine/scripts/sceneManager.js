class Status {
    constructor() {
        this.data = {
            'scene-manager': {},
            'characters'   : {},
            'chat-history' : [],
            errors: null,
        };

        // Event listeners
        this.listeners = {};
    }

    update(newStatus) {
        this.emitRecursive(newStatus);
        this.updateRecursive(newStatus);
    }

    emitRecursive(newStatus, basePath = '') {
        for (const [key, value] of Object.entries(newStatus)) {
            const fullPath = basePath ? `${basePath}/${key}` : key;

            if (typeof value === 'object' && value !== null) {
                this.emitRecursive(value, fullPath); // Recursively update nested paths
            }

            if (this.hasChanged(this.getNestedValue(this.data, fullPath), value)) {
                this.emit(fullPath, value); // Emit for the full path
            }
        }
    }

    updateRecursive(newStatus, basePath = '') {
        for (const [key, value] of Object.entries(newStatus)) {
            const fullPath = basePath ? `${basePath}/${key}` : key;
            if (this.hasChanged(this.getNestedValue(this.data, fullPath), value)) {
                this.setNestedValue(this.data, fullPath, value);
            }

            if (typeof value === 'object' && value !== null) {
                this.updateRecursive(value, fullPath); // Recursively update nested paths
            }
        }
    }

    hasChanged(oldData, newData) {
        return JSON.stringify(oldData) !== JSON.stringify(newData);
    }

    on(path, callback) {
        if (!this.listeners[path]) {
            this.listeners[path] = [];
        }
        this.listeners[path].push(callback);
    }

    emit(path, data) {
        // console.log('Emitting:', path, data);
        if (this.listeners[path]) {
            this.listeners[path].forEach((callback) => callback(data));
        }
    }

    getNestedValue(obj, path) {
        return path.split('/').reduce((acc, part) => (acc && acc[part] !== undefined ? acc[part] : undefined), obj);
    }

    setNestedValue(obj, path, value) {
        const parts = path.split('/');
        const lastPart = parts.pop();
        const target = parts.reduce((acc, part) => {
            if (!acc[part]) acc[part] = {};
            return acc[part];
        }, obj);
        target[lastPart] = value;
    }

    toJSON() {
        return this.data;
    }

    get(key) {
        const value = this.getNestedValue(this.data, key);
        if (value === undefined) {
            console.warn('Key not found:', key);
        }
        return value;
    }
}


function microphoneToggle(value) {
    var element = document.getElementById('microphone-button');

    if (value) {
        element.innerHTML = `<i class="bi-mic-fill"></i>`;
        element.classList.remove('btn-secondary');
        element.classList.add('btn-danger');
    } else {
        element.innerHTML = `<i class="bi-mic-mute-fill"></i>`;        
        element.classList.remove('btn-danger');
        element.classList.add('btn-secondary');
    }
}


class SceneManagerRenderer {
    constructor(sceneManager) {
        this.sceneManager = sceneManager;
        this.status = sceneManager.status;

        this.username = 'Patient';

        this.setupControls();
        this.setupUI();
    }

    setupControls() {
        document.querySelectorAll('[data-action]').forEach((element) => {
            const action = element.getAttribute('data-action');
            if (action === 'restart') {
                element.addEventListener('click', () => {
                    this.sceneManager.sendRestart();
                });
            } else if (action === 'photo') {
                element.addEventListener('click', () => {
                    this.sceneManager.takePhoto();
                });
            } else if (action === 'corpse') {
                element.addEventListener('click', () => {
                    const inputField = document.getElementById('chat-input-field');
                    inputField.setAttribute('disabled', 'disabled');
                    const message = "...";
                    inputField.value = '';
                    this.sceneManager.sendMessage(this.username, message);
                    inputField.removeAttribute('disabled'); 
                });

            } else if (action === 'fetch-status') {
                element.addEventListener('click', () => {
                    this.sceneManager.fetchStatus();
                });
            } else if (action === 'set-listening') {
                element.addEventListener('click', () => {
                    this.sceneManager.sendEvent('microphone', {'listening': 'toggle'});
                    // var listening = !sceneManager.status['data']['scene-manager']['listening'];
                    // sceneManager.status['data']['scene-manager']['listening'] = listening;
                    // microphoneToggle(listening);
                });
                this.sceneManager.status.on('scene-manager/listening', (value) => {
                    microphoneToggle(value);
                });
            } else if (action === 'chat-input') {
                this.setupChatControls(element);
            } else if (action === "scene-manager-transitions"){
                this.sceneManager.status.on('scene-manager/available-transitions', (transitions) => {
                    console.log('Received transitions update:', transitions);
                    this.updateTransitions(element, transitions);
                });
            } else {
                console.warn('Unknown action:', action);
            }

        });
    }

    setupUI() {
        document.querySelectorAll('[data-widget]').forEach((element) => {
            const data_id = element.getAttribute('data-widget');
            if (data_id === 'chat-history') {
                this.status.on(data_id, (value) => {
                    this.renderChatHistory(element, value);
                });
            } else if (data_id === 'scene-manager') {
                this.setupSceneInfo(element);
            } else if (data_id === 'characters') {
                this.renderCharacters(element);
            } else if (data_id === 'users') {
                this.renderUsers(element);
            } else if (data_id === 'scene-manager.diagram-uri') {
                this.setupSvg(data_id, element);
            } else {
                const key = data_id.replace(/\./g, '/');
                console.log('Setting up generic:', data_id, key);
                this.status.on(key, (value) => {
                    this.renderGeneric(element, value);
                });
            }
        });

        document.querySelectorAll('[data-bind]').forEach((element) => {
            const data_id = element.getAttribute('data-bind');
            const key = data_id.replace(/\./g, '/');
            console.log('Setting up generic:', data_id, key);
            this.status.on(key, (value) => {
                this.renderGeneric(element, value);
            });
        });
    }


    setupChatControls(element) {
        if (element.innerHTML === '') {
            element.innerHTML = `
            <form id="chat-form" action="#" class="d-flex">
                <input type="text" id="chat-input-field" class="form-control me-2">
                <button type="submit" class="btn btn-primary"><i class="bi-send"></i></button>
                <button id="chat-form-corpse" type="button" class="btn btn-success"><i class="bi-three-dots"></i></button>
            </form>
            `;

            element.querySelector('#chat-form').addEventListener('submit', (event) => {
                event.preventDefault();
                const inputField = element.querySelector('#chat-input-field');
                inputField.setAttribute('disabled', 'disabled');
                const message = inputField.value;
                inputField.value = '';
                this.sceneManager.sendMessage(this.username, message);
                inputField.removeAttribute('disabled'); 
            });

            element.querySelector('#chat-form-corpse').addEventListener('click', (event) => {
                const inputField = element.querySelector('#chat-input-field');
                inputField.setAttribute('disabled', 'disabled');
                const message = "...";
                inputField.value = '';
                this.sceneManager.sendMessage(this.username, message);
                inputField.removeAttribute('disabled'); 

            });
        }
    }

    updateTransitions(element, transitions) {
        console.log('Updating transitions:', transitions);
        element.innerHTML = '';

    
        for (const [i, transition] of Object.entries(transitions)) {
            const button = document.createElement('button');
            button.setAttribute('data-transition', transition);   

            if (transition === 'manual_fault') {
                button.className = 'btn btn-danger';
            } else {
                button.className = 'btn btn-warning';
            }
            button.maxWidth = '10%';
            button.style.overflow = 'hidden';
            button.style.textOverflow = 'ellipsis';


            button.id = `transition-button-${i}`;
            button.textContent = transition;
    
            element.appendChild(button);
            button.addEventListener('click', () => {
                this.sceneManager.sendEvent('transition', { transition });
            });
        }

        this.sceneManager.status.on('scene-manager/automatic-conditions', (value) => {
            // console.log('Automatic conditions:', value);
            for (const [i, transition] of Object.entries(transitions)) {
                const buttonId = `transition-button-${i}`;
                const button = document.getElementById(buttonId);

                if (!button) {
                    console.warn('Button not found:', buttonId);    
                    continue;
                }

                if (Array.isArray(value) && value.length > 0) {

                    if (value[0]['condition'] === "wait_for_manual") {
                        console.log('Setting button to wait_for_manual:', buttonId);
                        button.classList.remove('btn-warning');
                        button.classList.add('btn-success');
                    } else {
                        button.classList.remove('btn-success');
                        button.classList.add('btn-warning');
                    }
                } else {
                    console.log('Setting button to default:', buttonId);
                }

            }
        });
            
        
    }

    getCopyToClipboardButton(id) {
        const button = document.createElement('a');

        button.className = 'icon-link icon-link-hover';
        button.style = '--bs-icon-link-transform: translate3d(0, -.125rem, 0);';
        button.innerHTML = `<i class="bi-clipboard"></i>`;
                
        button.addEventListener('click', () => {
            const text = document.getElementById(id).textContent;
            console.log('Copying to clipboard:', id, text);
            navigator.clipboard.writeText(text);
        });
        return button;
    }

    setupSceneInfo(elem) {
        elem.innerHTML = ''; // Clear the existing content

        const table = document.createElement('table');
        table.className = 'table table-striped table-hover table-sm';
        table.style.fontSize = '0.7em';
        const tbody = document.createElement('tbody');

  
        const attributes = {
            "Scene"             : "state",
            "Exits"             : "automatic-conditions",
            "Scene Meta"        : "scene-meta",
            "Scene File"        : "current-scene-file",
            "Log Path"          : "output-path",
            "Listening"         : "listening",
            "Start"             : "start-time",
            "Last"              : "last-scene-change",
            "Duration"          : "time-since-last-scene-change",
            "Infered"           : "cached-infered-values"
            // "Metrics"           : "metrics"
        };

        for (const [label, key] of Object.entries(attributes)) {
            const row = document.createElement('tr');
            row.id = `scene-info-` + key.replace(/ /g, '-').toLowerCase();
            const value_id = row.id + '-value'; 

            if(["scene-meta", "metrics", "cached-infered-values"] .includes(key)){
                row.innerHTML = `
                    <td><strong>${label}</strong></td>
                    <td id="${value_id}" colspan="2"></td>
                `;

                const cell = row.querySelector('td:last-child');
                const nestedTable = document.createElement('table');
                nestedTable.className = 'table table-sm';
                const nestedTbody = document.createElement('tbody');
                nestedTable.appendChild(nestedTbody);
                cell.appendChild(nestedTable);
                tbody.appendChild(row);

                this.status.on('scene-manager/' + key, (value) => {
                    nestedTbody.innerHTML = '';
                    for (const [metaKey, metaValue] of Object.entries(value)) {
                        const metaValueId = `${value_id}-${metaKey.replace(/ /g, '-').toLowerCase()}`;
                        const metaRow = document.createElement('tr');
                        if ((metaKey != "initial") && (metaKey != "final")) {
                            metaRow.innerHTML = `
                                <td><strong>${metaKey}</strong></td>
                                <td id="${metaValueId}" >${this.formatValue(metaValue)}</td>
                                <td></td>
                            `;
                            const buttonCell = metaRow.querySelector('td:last-child');
                            buttonCell.appendChild(this.getCopyToClipboardButton(metaValueId));
                            nestedTbody.appendChild(metaRow);
                        }
                    }
                });

            } else if ([ "automatic-conditions"].includes(key)) {
                row.innerHTML = `
                    <td><strong>${label}</strong></td>
                    <td id="${value_id}" colspan="2"></td>
                `;  

                const cell = row.querySelector('td:last-child');
                const list = document.createElement('ul');
                list.className = 'list-group';
                cell.appendChild(list);
                tbody.appendChild(row);

                this.status.on('scene-manager/' + key, (value) => {
                    list.innerHTML = '';
                    for (const metaValue of value) {
                        const listItem = document.createElement('li');
                        listItem.className = 'list-group-item';
                        if (metaValue['condition'] === 'wait_for_manual') {
                            listItem.innerHTML = `<strong>${metaValue['target']}</strong>&nbsp<span class="badge text-bg-danger">${metaValue['condition']}</span>`;
                        } else if (metaValue['condition'] === 'complete') {
                            listItem.innerHTML = `<strong>${metaValue['target']}</strong>&nbsp<span class="badge text-bg-secondary">${metaValue['condition']}</span>`;
                        } else {
                            listItem.innerHTML = `<strong>${metaValue['target']}</strong>&nbsp<span class="badge text-bg-success">${metaValue['condition']}</span>`;
                        }
                        list.appendChild(listItem);
                    }
                });
            } else {
                row.innerHTML = `
                    <td><strong>${label}</strong></td>
                    <td id="${value_id}"></td>
                    <td></td>
                `;
                const buttonCell = row.querySelector('td:last-child');
                buttonCell.appendChild(this.getCopyToClipboardButton(value_id));
                tbody.appendChild(row);

                this.status.on('scene-manager/' + key, (value) => {
                    const valueElement = document.getElementById(value_id);
                    valueElement.innerHTML = this.formatValue(value);
                });
            }    
        }
    
        table.appendChild(tbody);
    
        elem.appendChild(table);
    }

    formatValue(value) {
        let formattedValue = `<span class="d-inline-block text-truncate" style="max-width: 300px;">`;
        if (typeof value === 'object') {
            formattedValue += `<pre>${JSON.stringify(value, null, 2)}</pre>`;
        } else if (value === null || value === undefined) {
            formattedValue += 'N/A';
        } else if (typeof value === 'number') {    
            formattedValue += value.toFixed(4);
        } else {
            formattedValue += value.toString();
        }
        formattedValue += `</span>`;
        
        return formattedValue;
    }

    renderCharacters(elem) {
        elem.innerHTML = '';
        this.status.on('characters', (characters) => {
            let allTableIds = [];

            for (const [ckey, value] of Object.entries(characters)) {
                console.log('Rendering character:', ckey, value);
                const cpath = ckey.replace(/ /g, '-').toLowerCase();
                const tableid = `character-info-` + cpath;

                let table = document.getElementById(tableid);
                let tbody = null;
                if ( !table ) {
                    table = document.createElement('table');
                
                    table.id = tableid;
                    table.className = 'table table-striped table-hover table-sm';
                    table.style.fontSize = '0.7em';
                    const thead = document.createElement('thead');
                    thead.innerHTML = `
                        <tr>
                            <th>Character</th>
                            <th>${cpath}</th>
                            <th></th>
                        </tr>
                    `;
                    table.appendChild(thead);


                }
            
                tbody = table.querySelector('tbody');
                if (!tbody) {
                    tbody = document.createElement('tbody');
                    table.appendChild(tbody);
                }
                tbody.innerHTML = '';

                const attributes = {
                    "Name"                 : "full-name",
                    "Behavior"             : "behavior",
                    "LLM"                  : "llm-name",
                    "Emotion"              : "emotion",
                    // "Observations"          : "observations",
                    "Speech style"         : "speech-style",
                    "State"                : "state",
                    "File"                 : "current-behavior-file",
                    "Progress"             : "speak_counter",
                    "Meta"                 : "scene_metadata",    

                };

                for (const [label, key] of Object.entries(attributes)) {
                    const row = document.createElement('tr');
                    row.id = `character-info-` + ckey + "-" + key.replace(/ /g, '-').toLowerCase();
                    const value_id = row.id + '-value';

                    if (key === "speak_counter") {
                        const maxIter = value['scene_metadata']['max-iterations'];
                        if( maxIter === null || maxIter === undefined) {
                            row.innerHTML = `
                                <td><strong>${label}</strong></td>
                                <td id="${value_id}">
                                </td>
                                <td></td>
                            `;
                        } else {
                            let progress = value[key]/maxIter;
                            // Clamp this value to 0.0 - 1.0
                            progress = Math.min(1.0, Math.max(0.0, progress)) * 100;
                            row.innerHTML = `
                                <td><strong>${label}</strong></td>
                                <td id="${value_id}">
                                    <div class="progress" role="progressbar" aria-label="Basic example" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                                        <div class="progress-bar" style="width: ${progress}%"></div>
                                    </div>
                                </td>
                                <td></td>
                            `;
                        }

                        const buttonCell = row.querySelector('td:last-child');
                        buttonCell.appendChild(this.getCopyToClipboardButton(value_id));

                        tbody.appendChild(row);
                        
                        const path = 'characters/' + ckey + "/" + key;
                        // console.log('Setting up listener:', path);
                        this.status.on(path, (value) => {
                            // console.log('Updating character data:', value_id);
                            const valueElement = document.getElementById(value_id);
                            if (valueElement) {
                                valueElement.textContent = this.formatValue(value);
                            }
                        });
                    } else {
                        row.innerHTML = `
                            <td><strong>${label}</strong></td>
                            <td id="${value_id}">${this.formatValue(value[key])}</td>
                            <td></td>
                        `;

                        const buttonCell = row.querySelector('td:last-child');
                        buttonCell.appendChild(this.getCopyToClipboardButton(value_id));

                        tbody.appendChild(row);
                        
                        const path = 'characters/' + ckey + "/" + key;
                        // console.log('Setting up listener:', path);
                        this.status.on(path, (value) => {
                            // console.log('Updating character data:', value_id);
                            const valueElement = document.getElementById(value_id);
                            if (valueElement) {
                                valueElement.textContent = this.formatValue(value);
                            }
                        });
                    }
                }
                
                elem.appendChild(table);
                allTableIds.push(tableid);
            }

            const allTables = elem.querySelectorAll('table');
            for (const table of allTables) {
                if (!allTableIds.includes(table.id)) {
                    table.remove();
                }
            }
        });   
    }


    renderUsers(elem) {
        elem.innerHTML = '';
        this.status.on('users', (users) => {
            let allTableIds = [];

            for (const [ckey, value] of Object.entries(users)) {
                console.log('Rendering users:', ckey, value);
                const cpath = ckey.replace(/ /g, '-').toLowerCase();
                const tableid = `user-info-` + cpath;

                let table = document.getElementById(tableid);
                let tbody = null;
                if ( !table ) {
                    table = document.createElement('table');
                
                    table.id = tableid;
                    table.className = 'table table-striped table-hover table-sm';
                    table.style.fontSize = '0.7em';
                    const thead = document.createElement('thead');
                    thead.innerHTML = `
                        <tr>
                            <th>User</th>
                            <th>${cpath}</th>
                            <th></th>
                        </tr>
                    `;
                    table.appendChild(thead);
                }
            
                tbody = table.querySelector('tbody');
                if (!tbody) {
                    tbody = document.createElement('tbody');
                    table.appendChild(tbody);
                }
                tbody.innerHTML = '';

                const attributes = {
                    "Name"                 : "full-name",
                    "Emotion"              : "emotion",
                    "Observations"         : "observations",
                };

                for (const [label, key] of Object.entries(attributes)) {
                    const row = document.createElement('tr');
                    row.id = `user-info-` + ckey + "-" + key.replace(/ /g, '-').toLowerCase();
                    const value_id = row.id + '-value';

                    row.innerHTML = `
                        <td><strong>${label}</strong></td>
                        <td id="${value_id}">${this.formatValue(value[key])}</td>
                        <td></td>
                    `;

                    const buttonCell = row.querySelector('td:last-child');
                    buttonCell.appendChild(this.getCopyToClipboardButton(value_id));

                    tbody.appendChild(row);
                    
                    const path = 'users/' + ckey + "/" + key;
                    // console.log('Setting up listener:', path);
                    this.status.on(path, (value) => {
                        // console.log('Updating character data:', value_id);
                        const valueElement = document.getElementById(value_id);
                        if (valueElement) {
                            valueElement.textContent = this.formatValue(value);
                        }
                    });

                }
                
                elem.appendChild(table);
                allTableIds.push(tableid);
            }

            const allTables = elem.querySelectorAll('table');
            for (const table of allTables) {
                if (!allTableIds.includes(table.id)) {
                    table.remove();
                }
            }
        });   
    }

    renderChatHistory(elem, chatHistory, reversed = true) {
        elem.innerHTML = '';
        if (reversed) {
            chatHistory = chatHistory.slice().reverse();
        }

        for (const message of chatHistory) {
            let line = '';
            if (message['type'] === 'chat') {
                line = `<p><strong>${message['name']}</strong>: ${message['message']}</p>`;
            } else if (message['type'] === 'scene-change') {
                line = `<div class="p-2 bg-primary-subtle border border-primary-subtle mb-2">`;
                line += `<p><strong>Scene -  ${message['scene']}</strong></p>`
                for (const [key, value] of Object.entries(message['meta'])) {
                    if (key === 'initial' || key === 'final') {
                        continue;
                    }
                    if (typeof value === 'object') {
                        line += `<p class="m-0"><em>${key}</em>: ${ JSON.stringify(value, null, 2)}</p>`;
                    } else {
                        line += `<p class="m-0"><em>${key}</em>: ${value}<br></p>`;
                    }
                }
                line += `</div>`;
            } else if (message['type'] === 'bot-instantiation') {

                line = `<div class="p-2 bg-secondary-subtle border border-secondary-subtle mb-2">`;
                line += `<p class="m-0"><strong>${message['name']}:</strong>`
                line += `<p class="px-3 mt-0 mb-0"><em>Behaviour:</em> ${message['persona']}</p>`;
                line += `<p class="px-3 mt-0 mb-0"><em>Persona:</em> ${message['behavior']}</p>`;
                line += `</div>`;
            } else if (message['type'] === 'meatstate') {
                line = `<p class="text-secondary-emphasis"><strong>${message['name']}</strong>: [${message['message']}]</em></p>`;
            }
            elem.innerHTML = line + elem.innerHTML;
        }

        if (reversed)   {
            elem.scrollTop = elem.scrollHeight;
        }
    }

    setupSvg(id, element) {
        
        if (element.innerHTML === '') {
            element.innerHTML = `
            <embed src="" id="${id}" alt="Scene Manager Diagram" class="img-fluid"  type="image/svg+xml">
            `;
        }

        const key = id.replace(/\./g, '/');
        console.log('Setting up SVG:', id, key);
        this.status.on(key, (value) => {
            console.log('Updating SVG:', id, value);
            const embed = document.getElementById(id);
            value += '?' + new Date().getTime();
            embed.setAttribute('src', value);
        });

    }


    renderGeneric(element, value) {
        console.log('Rendering generic:', element, value);
        if (typeof value === 'object') {
            element.textContent = JSON.stringify(value, null, 2);
        } else {
            element.textContent = value || '';
        }
    }
}

class SceneManager {
    constructor(apiBaseUrl) {
        this.socketAddress = apiBaseUrl;
        this.apiBaseUrl   = apiBaseUrl;
        this.apiPhotoUrl  = "http://127.0.0.1:8025";

        this.status = new Status();

        this.socket = io.connect(this.socketAddress);
        this.socket.on('connect', this.onConnect.bind(this));
        this.socket.on('stream-status', this.onStatus.bind(this));

        this.renderer = new SceneManagerRenderer(this);
    }


    onConnect() {
        console.log('Connected', this.socket.id, this.socketAddress);
    }

    onStatus(status) {
        this.updateStatus(status);
    }

    updateStatus(status) {
        this.status.update(status);
    }

    async fetchStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/status`);
            const data     = await response.json();
            this.updateStatus(data);
        } catch (error) {
            console.error('Error fetching status:', error);
        }
    }


    async sendRestart() {
        try {
            const response     = await fetch(`${this.apiBaseUrl}/restart`);
            const responseData = await response.json();
            this.updateStatus(responseData);
        } catch (error) {
            console.error('Error sending restart:', error);
        }
        
    }

    async sendEvent(action, data = {}) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/message`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    command: 'event',
                    data: { action, ...data },
                }),
            });
            const responseData = await response.json();
            this.updateStatus(responseData);
        } catch (error) {
            console.error('Error sending request:', error);
        }
    }
    async takePhoto() {
        try {
            console.log('Taking photo');
            const response = await fetch(`${this.apiPhotoUrl}/capture_no`, {
                method: 'GET',
                signal: AbortSignal.timeout(100),
            });
            console.log(response);
        } catch (error) {
            console.error('Error sending request:', error);
        }
    }

    async sendMessage(username, message) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/message`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    'command': 'chat',
                    'data': {
                        'message':  message,
                        'user': username
                    }
                }),
            });
            const responseData = await response.json();
            this.updateStatus(responseData);
        } catch (error) {
            console.error('Error sending message:', error);
        }
    }
}


var sceneManager;

// Initialize the ApiManager
document.addEventListener('DOMContentLoaded', () => {
    const socketAddress = 'http://' + document.domain + ':' + location.port;
    sceneManager = new SceneManager(socketAddress);

});