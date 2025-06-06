// Main JavaScript for Odoo Developer Tools UI

// Document ready function
document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle
    const sidebarCollapse = document.getElementById('sidebarCollapse');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    
    // Function to toggle sidebar
    function toggleSidebar() {
        sidebar.classList.toggle('active');
        
        // Create/remove overlay for mobile
        if (window.innerWidth <= 768) {
            if (sidebar.classList.contains('active')) {
                const overlay = document.createElement('div');
                overlay.classList.add('overlay');
                document.body.appendChild(overlay);
                
                // Add active class after a small delay to allow animation
                setTimeout(() => {
                    overlay.classList.add('active');
                }, 10);
                
                // Close sidebar when clicking overlay
                overlay.addEventListener('click', toggleSidebar);
            } else {
                const overlay = document.querySelector('.overlay');
                if (overlay) {
                    overlay.classList.remove('active');
                    
                    // Remove overlay after transition
                    setTimeout(() => {
                        overlay.remove();
                    }, 300);
                }
            }
        }
    }
    
    if (sidebarCollapse) {
        sidebarCollapse.addEventListener('click', toggleSidebar);
    }
    
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', toggleSidebar);
    }
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const closeButton = alert.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            }
        }, 5000);
    });
    
    // File input enhancement
    const fileInputs = document.querySelectorAll('.custom-file-input');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            const fileName = this.files[0]?.name || 'No file chosen';
            const label = document.querySelector(`label[for="${this.id}"]`);
            if (label) {
                label.textContent = fileName;
            }
        });
    });
    
    // Copy SSH command to clipboard
    const sshCommandButtons = document.querySelectorAll('.copy-ssh-command');
    sshCommandButtons.forEach(button => {
        button.addEventListener('click', function() {
            const host = this.getAttribute('data-host');
            
            fetch(`/servers/generate_command/${host}`)
                .then(response => response.json())
                .then(data => {
                    if (data.command) {
                        navigator.clipboard.writeText(data.command)
                            .then(() => {
                                // Change button text briefly
                                const originalText = this.innerHTML;
                                this.innerHTML = '<i class="fas fa-check"></i> Copied!';
                                setTimeout(() => {
                                    this.innerHTML = originalText;
                                }, 2000);
                            })
                            .catch(err => {
                                console.error('Could not copy text: ', err);
                                alert('Failed to copy to clipboard. Try again or copy manually.');
                            });
                    } else {
                        alert('Could not generate SSH command');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while generating the SSH command');
                });
        });
    });
    
    // Connect to SSH server using terminal
    const connectButtons = document.querySelectorAll('.connect-ssh-server');
    connectButtons.forEach(button => {
        button.addEventListener('click', function() {
            const host = this.getAttribute('data-host');
            const button = this;
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Connecting...';
            button.disabled = true;
            
            fetch(`/servers/generate_command/${host}`)
                .then(response => response.json())
                .then(data => {
                    if (data.command) {
                        const command = data.command;
                        // Create a form to submit the command as POST
                        const form = document.createElement('form');
                        form.method = 'post';
                        form.action = '/servers/connect';
                        form.style.display = 'none';
                        
                        // Add the command
                        const commandInput = document.createElement('input');
                        commandInput.type = 'hidden';
                        commandInput.name = 'command';
                        commandInput.value = command;
                        form.appendChild(commandInput);
                        
                        // Add server information for enhanced UI
                        const serverHostInput = document.createElement('input');
                        serverHostInput.type = 'hidden';
                        serverHostInput.name = 'server_host';
                        serverHostInput.value = data.host || host;
                        form.appendChild(serverHostInput);
                        
                        const authTypeInput = document.createElement('input');
                        authTypeInput.type = 'hidden';
                        authTypeInput.name = 'auth_type';
                        authTypeInput.value = data.auth_type || 'key';
                        form.appendChild(authTypeInput);
                        
                        if (data.user) {
                            const userInput = document.createElement('input');
                            userInput.type = 'hidden';
                            userInput.name = 'user';
                            userInput.value = data.user;
                            form.appendChild(userInput);
                        }
                        
                        if (data.hostname) {
                            const hostnameInput = document.createElement('input');
                            hostnameInput.type = 'hidden';
                            hostnameInput.name = 'hostname';
                            hostnameInput.value = data.hostname;
                            form.appendChild(hostnameInput);
                        }
                        
                        document.body.appendChild(form);
                        form.submit();
                    } else {
                        // Reset button if error
                        button.innerHTML = '<i class="fas fa-terminal me-1"></i> Connect';
                        button.disabled = false;
                        alert('Error connecting to SSH server: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    // Reset button if error
                    button.innerHTML = '<i class="fas fa-terminal me-1"></i> Connect';
                    button.disabled = false;
                    console.error('Error:', error);
                    alert('Error connecting to SSH server');
                });
        });
    });
    
    // Confirm database drop
    const confirmDropForm = document.getElementById('confirm-drop-form');
    if (confirmDropForm) {
        confirmDropForm.addEventListener('submit', function(e) {
            if (!confirm('Are you sure you want to drop this database and its filestore? This action cannot be undone!')) {
                e.preventDefault();
                return false;
            }
        });
    }
    
    // Refresh database list
    const refreshDbButton = document.getElementById('refresh-db-list');
    if (refreshDbButton) {
        refreshDbButton.addEventListener('click', function() {
            window.location.reload();
        });
    }
});
