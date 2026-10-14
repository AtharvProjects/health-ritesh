// Global UI Interactions and Smooth Scrolling
document.addEventListener('DOMContentLoaded', function () {
    // 1. Smooth Scrolling for Landing Page Links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(link => {
        link.addEventListener('click', function (e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // 2. Active Navigation Class Highlight on Scroll
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link[href^="#"]');
    
    function highlightNavigation() {
        let scrollY = window.pageYOffset;
        
        sections.forEach(current => {
            const sectionHeight = current.offsetHeight;
            const sectionTop = current.offsetTop - 100;
            const sectionId = current.getAttribute('id');
            
            if (scrollY > sectionTop && scrollY <= sectionTop + sectionHeight) {
                navLinks.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === '#' + sectionId) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }

    if (sections.length > 0 && navLinks.length > 0) {
        window.addEventListener('scroll', highlightNavigation);
    }

    // 3. Dynamic search/filter helper for frontend tables
    // If a page has an input with class 'table-search' and a table, it will filter rows
    const searchInput = document.querySelector('.table-search');
    if (searchInput) {
        searchInput.addEventListener('keyup', function () {
            const query = this.value.toLowerCase();
            const tableRows = document.querySelectorAll('.table tbody tr');
            
            tableRows.forEach(row => {
                // Skip header row
                if (row.querySelector('th')) return;
                
                const cells = row.querySelectorAll('td');
                let match = false;
                cells.forEach(cell => {
                    if (cell.textContent.toLowerCase().includes(query)) {
                        match = true;
                    }
                });
                
                if (match) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // 4. Setup Automatic Copyright Year
    const yearEl = document.getElementById('current-year');
    if (yearEl) {
        yearEl.textContent = new Date().getFullYear();
    }

    // 5. Dynamic Table Formatting: Cryptographic Badges and Status Pills
    const tableCells = document.querySelectorAll('.table td');
    tableCells.forEach(cell => {
        // Skip formatting if cell has buttons/links/interactive structures
        if (cell.children.length > 0) return;

        const text = cell.textContent.trim();

        // 5.1 Format Ethereum Addresses (Starts with '0x', length 42)
        if (text.startsWith('0x') && text.length === 42) {
            cell.innerHTML = `<code class="eth-address" title="Click to copy Address: ${text}" onclick="navigator.clipboard.writeText('${text}'); alert('Ethereum address copied to clipboard!');">${text.substring(0, 6)}...${text.substring(38)}</code>`;
            return;
        }

        // 5.2 Format IPFS Hashes (Starts with 'Qm' or '[LEGACY] Qm')
        const ipfsMatch = text.match(/(Qm[1-9A-HJ-NP-Za-km-z]{44})/);
        if (ipfsMatch) {
            const rawHash = ipfsMatch[1];
            const prefix = text.includes('[LEGACY]') ? '[LEGACY] ' : '';
            cell.innerHTML = `${prefix}<code class="ipfs-hash" title="Click to copy IPFS Hash: ${rawHash}" onclick="navigator.clipboard.writeText('${rawHash}'); alert('IPFS hash copied to clipboard!');">${rawHash.substring(0, 8)}...${rawHash.substring(38)}</code>`;
            return;
        }

        // 5.3 Format Status Texts
        if (text === 'Locked' || text === 'Locked & Prescribed') {
            cell.innerHTML = `<span class="custom-badge badge-locked">${text}</span>`;
        } else if (text === 'Open' || text === 'Unlocked' || text === 'Active' || text === 'Yes') {
            cell.innerHTML = `<span class="custom-badge badge-open">${text}</span>`;
        } else if (text === 'Shared' || text === 'Shared with clinic') {
            cell.innerHTML = `<span class="custom-badge badge-shared">${text}</span>`;
        } else if (text === 'None') {
            cell.innerHTML = `<span class="text-secondary small">None</span>`;
        }
    });

    // 6. Dynamic Page Preloader Injection and Action Spinner
    const preloaderHTML = `
        <div class="page-loader fade-out" id="pageLoader">
            <div class="loader-content">
                <div class="loader-spinner"></div>
                <p class="loader-text" id="loaderText">Loading SafeHealth...</p>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('afterbegin', preloaderHTML);

    const loader = document.getElementById('pageLoader');
    const loaderText = document.getElementById('loaderText');

    function dismissLoader() {
        if (loader) {
            loader.classList.add('fade-out');
        }
    }

    // Dismiss loader once page is ready
    if (document.readyState === 'complete') {
        dismissLoader();
    } else {
        window.addEventListener('load', dismissLoader);
        setTimeout(dismissLoader, 500);
    }

    // Intercept form submissions to provide live feedback for slow Web3 transactions
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function () {
            if (loader && loaderText) {
                const action = form.getAttribute('action') || '';
                if (action.includes('Register') || action.includes('Upload') || action.includes('Share') || action.includes('Submit') || action.includes('Create') || action.includes('Action')) {
                    loaderText.textContent = "Securing transaction on Blockchain ledger...";
                } else {
                    loaderText.textContent = "Processing request... Please wait";
                }
                loader.classList.remove('fade-out');
            }
        });
    });

    // 7. Manage Share Record Checkbox Actions (Search Filter, Select/Clear all)
    const shareContainer = document.getElementById('shareOrgsContainer');
    if (shareContainer) {
        const shareSearch = document.getElementById('shareOrgSearch');
        const selectAllShare = document.getElementById('selectAllShareOrgs');
        const clearAllShare = document.getElementById('clearAllShareOrgs');
        const shareForm = document.getElementById('shareRecordForm');

        const checkboxes = shareContainer.querySelectorAll('.share-org-cb');

        if (selectAllShare) {
            selectAllShare.addEventListener('click', function() {
                checkboxes.forEach(cb => cb.checked = true);
            });
        }

        if (clearAllShare) {
            clearAllShare.addEventListener('click', function() {
                checkboxes.forEach(cb => cb.checked = false);
            });
        }

        if (shareSearch) {
            shareSearch.addEventListener('keyup', function() {
                const query = this.value.toLowerCase();
                shareContainer.querySelectorAll('.share-org-item').forEach(item => {
                    const label = item.querySelector('label').textContent.toLowerCase();
                    item.style.display = label.includes(query) ? '' : 'none';
                });
            });
        }

        if (shareForm) {
            shareForm.addEventListener('submit', function(e) {
                const anyChecked = Array.from(checkboxes).some(cb => cb.checked);
                if (!anyChecked) {
                    e.preventDefault();
                    alert('Please select at least one organization to share this medical record with.');
                    const card = shareContainer.closest('.card');
                    card.style.borderColor = 'var(--danger-color)';
                    
                    // Stop spinner since submission was cancelled
                    if (loader) {
                        loader.classList.add('fade-out');
                    }
                }
            });
        }
    }
});


