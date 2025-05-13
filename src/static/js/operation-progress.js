/**
 * Operation Progress Bar
 * Handles displaying and updating progress bars for long-running operations
 */

// Configure the progress bar simulation
const progressConfig = {
    'extend-enterprise': {
        steps: ['Scanning databases', 'Identifying Enterprise databases', 'Updating expiration dates', 'Finalizing'],
        durations: [2000, 2000, 3000, 1000]
    },
    'drop-database': {
        steps: ['Terminating connections', 'Removing database', 'Removing filestore', 'Finalizing'],
        durations: [1500, 2000, 2500, 1000]
    },
    'restore-database': {
        steps: ['Extracting backup', 'Creating database', 'Importing data', 'Restoring filestore', 'Applying settings', 'Finalizing'],
        durations: [3000, 1500, 5000, 4000, 2000, 1000]
    }
};

/**
 * Initialize a progress bar for a specific operation
 * @param {string} operationType - The type of operation (extend-enterprise, drop-database, restore-database)
 * @param {string} formId - The ID of the form that triggers the operation
 */
function initOperationProgress(operationType, formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    // Create progress bar container if it doesn't exist
    let progressContainer = document.querySelector('.operation-progress');
    if (!progressContainer) {
        progressContainer = document.createElement('div');
        progressContainer.className = 'operation-progress';
        progressContainer.innerHTML = `
            <div class="operation-status"></div>
            <div class="progress">
                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                     role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"
                     style="width: 0%">0%</div>
            </div>
        `;
        form.parentNode.insertBefore(progressContainer, form.nextSibling);
    }
    
    // Handle form submission
    form.addEventListener('submit', function(e) {
        // Don't prevent form submission - we want the actual operation to proceed
        // Just start showing the progress bar as visual feedback
        
        const progressBar = document.querySelector('.progress-bar');
        const statusText = document.querySelector('.operation-status');
        const config = progressConfig[operationType];
        
        if (!config) return;
        
        // Hide the form and show the progress
        form.style.display = 'none';
        progressContainer.style.display = 'block';
        
        let currentStep = 0;
        let totalSteps = config.steps.length;
        let progressPerStep = 100 / totalSteps;
        
        // Update progress for each step
        function updateProgress() {
            if (currentStep >= totalSteps) return;
            
            // Update status text
            statusText.textContent = config.steps[currentStep];
            
            // Calculate progress percentage
            let startProgress = currentStep * progressPerStep;
            let endProgress = (currentStep + 1) * progressPerStep;
            let duration = config.durations[currentStep];
            let startTime = Date.now();
            
            // Animate progress within the step
            function animateStep() {
                let elapsed = Date.now() - startTime;
                let progress = Math.min(elapsed / duration, 1);
                let currentProgress = startProgress + (progress * (endProgress - startProgress));
                
                // Update progress bar
                progressBar.style.width = currentProgress + '%';
                progressBar.setAttribute('aria-valuenow', currentProgress);
                progressBar.textContent = Math.round(currentProgress) + '%';
                
                if (progress < 1) {
                    requestAnimationFrame(animateStep);
                } else {
                    // Move to next step
                    currentStep++;
                    if (currentStep < totalSteps) {
                        setTimeout(updateProgress, 200); // Short delay between steps
                    }
                }
            }
            
            animateStep();
        }
        
        // Start progress animation
        updateProgress();
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check which operation page we're on
    if (document.getElementById('extend-enterprise-form')) {
        initOperationProgress('extend-enterprise', 'extend-enterprise-form');
    }
    
    if (document.getElementById('drop-database-form')) {
        initOperationProgress('drop-database', 'drop-database-form');
    }
    
    if (document.getElementById('restore-database-form')) {
        initOperationProgress('restore-database', 'restore-database-form');
    }
});
