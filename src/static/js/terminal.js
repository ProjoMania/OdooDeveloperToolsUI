// Initialize terminal
const term = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: 'monospace',
    theme: {
        background: '#1e1e1e',
        foreground: '#ffffff'
    }
});

// Connect to Socket.IO
const socket = io();

// Initialize terminal in the container
term.open(document.getElementById('terminal'));

// Handle terminal input
term.onData(data => {
    socket.emit('input', { data: data });
});

// Handle terminal resize
term.onResize(size => {
    socket.emit('resize', {
        cols: size.cols,
        rows: size.rows
    });
});

// Handle Socket.IO events
socket.on('connect', () => {
    // Get host from URL
    const host = window.location.pathname.split('/').pop();
    // Connect to SSH
    socket.emit('connect_ssh', { host: host });
});

socket.on('connected', data => {
    term.write('\r\n\x1B[1;32m' + data.message + '\x1B[0m\r\n');
});

socket.on('output', data => {
    term.write(data.data);
});

socket.on('error', data => {
    term.write('\r\n\x1B[1;31mError: ' + data.message + '\x1B[0m\r\n');
});

// Handle window resize
window.addEventListener('resize', () => {
    term.fit();
});

// Add this function to handle host key verification
function handleHostKeyVerification(data) {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'hostKeyModal';
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Host Key Verification</h5>
                </div>
                <div class="modal-body">
                    <p>The authenticity of host '${data.hostname}' can't be established.</p>
                    <p>${data.key_type} key fingerprint is:</p>
                    <pre>${data.key_fingerprint}</pre>
                    <p>Are you sure you want to continue connecting?</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">No</button>
                    <button type="button" class="btn btn-primary" id="acceptHostKey">Yes</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    const modalInstance = new bootstrap.Modal(modal);
    modalInstance.show();

    return new Promise((resolve) => {
        document.getElementById('acceptHostKey').addEventListener('click', () => {
            modalInstance.hide();
            modal.remove();
            resolve(true);
        });

        modal.addEventListener('hidden.bs.modal', () => {
            modal.remove();
            resolve(false);
        });
    });
}

// Update the WebSocket message handler
socket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'connected':
            term.write('\r\n\x1B[1;32m' + data.message + '\x1B[0m\r\n');
            break;
            
        case 'output':
            term.write(data.data);
            break;
            
        case 'error':
            term.write('\r\n\x1B[1;31mError: ' + data.message + '\x1B[0m\r\n');
            break;

        case 'host_key_verification':
            handleHostKeyVerification(data).then(accepted => {
                socket.send(JSON.stringify({
                    type: 'host_key_response',
                    accept: accepted
                }));
            });
            break;
            
        default:
            console.log('Unknown message type:', data.type);
    }
}; 