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
            
            fetch(`/ssh/generate_command/${host}`)
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
            
            fetch(`/ssh/generate_command/${host}`)
                .then(response => response.json())
                .then(data => {
                    if (data.command) {
                        const command = data.command;
                        // Create a form to submit the command as POST
                        const form = document.createElement('form');
                        form.method = 'post';
                        form.action = '/ssh/connect';
                        form.style.display = 'none';
                        
                        const input = document.createElement('input');
                        input.type = 'hidden';
                        input.name = 'command';
                        input.value = command;
                        
                        form.appendChild(input);
                        document.body.appendChild(form);
                        form.submit();
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An error occurred while connecting to the SSH server');
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
