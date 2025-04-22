document.addEventListener('DOMContentLoaded', function() {
    const itemsContainer = document.getElementById('itemsContainer');
    const searchInput = document.getElementById('searchInput');
    const categoryFilter = document.getElementById('categoryFilter');
    const sortSelect = document.getElementById('sortSelect');
    const modal = document.getElementById('itemModal');
    const modalContent = document.getElementById('modalContent');
    const closeButton = document.querySelector('.close-button');
    const excelFileInput = document.getElementById('excelFile');
    const uploadBtn = document.getElementById('uploadBtn');
    const fileNameDisplay = document.getElementById('fileNameDisplay');
    const loadedFilesList = document.getElementById('loadedFiles');
    const addItemBtn = document.getElementById('addItemBtn');
    const exportCsvBtn = document.getElementById('exportCsvBtn');
    const addItemModal = document.getElementById('addItemModal');
    const cancelAddItem = document.getElementById('cancelAddItem');
    const addCloseButton = document.querySelector('.add-close-button');
    const saveItemChanges = document.getElementById('saveItemChanges');
    const cancelItemChanges = document.getElementById('cancelItemChanges');
    const submitAddItemBtn = document.getElementById('submitAddItem');
    const newItemContainer = document.getElementById('newItemContainer');
    const deleteItemBtn = document.getElementById('deleteItemBtn'); // Get delete button
    const LOCAL_STORAGE_KEY = 'magicItemsAppState';

    let leagueItems = [];
    let loadedFiles = [];
    let currentSort = 'nameAsc';
    let currentEditingItem = null;

    function capitalize(text) {
        if (!text) return '';
        return text.split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }

    function generateUniqueId() {
        return Date.now() + '-' + Math.floor(Math.random() * 1000);
    }

    function saveStateToLocalStorage() {
        const state = {
            leagueItems: leagueItems,
            loadedFiles: loadedFiles
        };
        try {
            localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(state));
            console.log("State saved to local storage.");
        } catch (e) {
            console.error("Error saving state to local storage:", e);
        }
    }

    function loadStateFromLocalStorage() {
        try {
            const savedState = localStorage.getItem(LOCAL_STORAGE_KEY);
            if (savedState) {
                const state = JSON.parse(savedState);
                leagueItems = state.leagueItems || [];
                loadedFiles = state.loadedFiles || [];
                console.log("State loaded from local storage.");
                return true;
            }
        } catch (e) {
            console.error("Error loading state from local storage:", e);
            localStorage.removeItem(LOCAL_STORAGE_KEY);
        }
        return false;
    }

    function initializeApp() {
        if (loadStateFromLocalStorage()) {
            // If state loaded, update UI
            handleFilterAndSort();
            updateRegionFilter(leagueItems);
            updateLoadedFilesList();
        } else {
            // No saved state, try loading base-items.csv
            itemsContainer.innerHTML = '<div class="loading">Loading base items...</div>';
            fetchAndLoadBaseItems();
            updateLoadedFilesList(); // Show "No files loaded" initially
        }
    }

    // Function to fetch and load base-items.csv
    function fetchAndLoadBaseItems() {
        const baseFileName = 'base-items.csv';
        fetch(baseFileName)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.text();
            })
            .then(csvText => {
                Papa.parse(csvText, {
                    header: true,
                    delimiter: ";", // Explicitly set semicolon delimiter
                    skipEmptyLines: true,
                    complete: function(results) {
                        if (results.errors.length > 0) {
                            console.error('Base CSV parsing errors:', results.errors);
                            itemsContainer.innerHTML = `<div class="no-results">Error parsing base items: ${results.errors[0].message}. Please upload a file manually.</div>`;
                            return;
                        }

                        const fileInfo = {
                            name: baseFileName,
                            id: generateUniqueId(), // Give it a unique ID
                            count: results.data.length
                        };
                        // Avoid adding duplicate base file info if somehow loaded again
                        if (!loadedFiles.some(f => f.name === baseFileName)) {
                             loadedFiles.push(fileInfo);
                        }

                        const processedData = processCSVData(results.data, fileInfo.id);
                        leagueItems = [...leagueItems, ...processedData]; // Add base items

                        handleFilterAndSort();
                        updateRegionFilter(leagueItems);
                        updateLoadedFilesList();
                        saveStateToLocalStorage(); // Save state after loading base items
                        console.log(`Loaded ${baseFileName} automatically.`);
                    },
                    error: function(error) {
                        console.error(`Error parsing ${baseFileName}:`, error);
                        itemsContainer.innerHTML = `<div class="no-results">Error parsing ${baseFileName}. Please upload a file manually.</div>`;
                    }
                });
            })
            .catch(error => {
                console.error(`Error fetching ${baseFileName}:`, error);
                // Display a more user-friendly initial message if base file fails to load
                itemsContainer.innerHTML = '<div class="initial-message">Upload a CSV or add items manually</div>';
            });
    }

    uploadBtn.addEventListener('click', () => excelFileInput.click());
    excelFileInput.addEventListener('change', handleFileUpload);
    searchInput.addEventListener('input', handleFilterAndSort);
    categoryFilter.addEventListener('change', handleFilterAndSort);
    sortSelect.addEventListener('change', () => {
        currentSort = sortSelect.value;
        handleFilterAndSort();
    });

    closeButton.addEventListener('click', () => modal.style.display = 'none');
    addCloseButton.addEventListener('click', () => addItemModal.style.display = 'none');
    cancelAddItem.addEventListener('click', () => addItemModal.style.display = 'none');

    saveItemChanges.addEventListener('click', saveEditedItem);
    cancelItemChanges.addEventListener('click', () => modal.style.display = 'none');
    deleteItemBtn.addEventListener('click', deleteCurrentItem); // Add listener for delete button

    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            saveEditedItem();
        }
        if (event.target === addItemModal) {
            addItemModal.style.display = 'none';
        }
    });

    addItemBtn.addEventListener('click', () => {
        document.getElementById('newItemName').textContent = '';
        document.getElementById('newItemRegion').textContent = '';
        document.getElementById('newItemDescription').textContent = '';
        document.getElementById('newItemLore').textContent = '';
        document.getElementById('newItemImage').textContent = '';
        addItemModal.style.display = 'block';
    });

    submitAddItemBtn.addEventListener('click', function() {
        const itemName = document.getElementById('newItemName').textContent.trim();
        if (!itemName) {
            alert('Item Name is required.');
            return;
        }

        const newItem = {
            id: generateUniqueId(),
            name: itemName,
            region: capitalize(document.getElementById('newItemRegion').textContent.trim() || 'Unknown'),
            descriptionLore: document.getElementById('newItemDescription').textContent.trim() || '',
            lore: document.getElementById('newItemLore').textContent.trim() || '',
            image: document.getElementById('newItemImage').textContent.trim() || '',
            source: 'manual'
        };

        leagueItems.push(newItem);
        handleFilterAndSort();
        updateRegionFilter(leagueItems);
        addItemModal.style.display = 'none';
        updateLoadedFilesList();
        saveStateToLocalStorage();
    });

    exportCsvBtn.addEventListener('click', exportToCSV);

    function saveEditedItem() {
        if (!currentEditingItem) return;

        const editedTitle = document.getElementById('editItemTitle').textContent.trim();
        const editedRegion = document.getElementById('editItemRegion').textContent.trim();
        const editedDescription = document.getElementById('editItemDescription').textContent.trim();
        const editedLore = document.getElementById('editItemLore').textContent.trim();
        const editedImageUrl = document.getElementById('editItemImageUrl')?.value.trim() || currentEditingItem.image;

        const itemIndex = leagueItems.findIndex(item => item.id === currentEditingItem.id);
        if (itemIndex !== -1) {
            leagueItems[itemIndex].name = editedTitle;
            leagueItems[itemIndex].region = capitalize(editedRegion || 'Unknown');
            leagueItems[itemIndex].descriptionLore = editedDescription;
            leagueItems[itemIndex].lore = editedLore;
            leagueItems[itemIndex].image = editedImageUrl;

            modal.style.display = 'none';
            handleFilterAndSort();
            updateRegionFilter(leagueItems);
            saveStateToLocalStorage();
            currentEditingItem = null;
        } else {
            console.error("Could not find item to save:", currentEditingItem.id);
            modal.style.display = 'none';
            currentEditingItem = null;
        }
    }

    function deleteCurrentItem() {
        if (!currentEditingItem) return;

        const confirmation = window.confirm(`Are you sure you want to delete "${currentEditingItem.name}"? This cannot be undone.`);

        if (confirmation) {
            const itemIndex = leagueItems.findIndex(item => item.id === currentEditingItem.id);
            if (itemIndex !== -1) {
                leagueItems.splice(itemIndex, 1); // Remove item from array

                // Update UI and save state
                modal.style.display = 'none';
                handleFilterAndSort();
                updateRegionFilter(leagueItems);
                updateLoadedFilesList();
                saveStateToLocalStorage();
                console.log(`Item "${currentEditingItem.name}" deleted.`);
                currentEditingItem = null; // Reset editing item
            } else {
                console.error("Could not find item to delete:", currentEditingItem.id);
                alert("Error: Could not find the item to delete.");
                modal.style.display = 'none'; // Still close modal
                currentEditingItem = null;
            }
        } else {
            console.log("Deletion cancelled.");
        }
    }

    function handleFilterAndSort() {
        const filteredItems = filterItems();
        const sortedItems = sortItems(filteredItems, currentSort);
        displayItems(sortedItems);
    }

    function sortItems(items, sortOrder) {
        return [...items].sort((a, b) => {
            switch(sortOrder) {
                case 'nameAsc':
                    return a.name.localeCompare(b.name);
                case 'nameDesc':
                    return b.name.localeCompare(a.name);
                case 'regionAsc':
                    return a.region.localeCompare(b.region) || a.name.localeCompare(b.name);
                case 'regionDesc': // Added Region Z-A sorting
                    return b.region.localeCompare(a.region) || a.name.localeCompare(b.name);
                default:
                    return 0;
            }
        });
    }

    function handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        if (loadedFiles.some(f => f.name === file.name)) {
            alert(`File "${file.name}" is already loaded.`);
            excelFileInput.value = '';
            return;
        }

        itemsContainer.innerHTML = '<div class="loading">Loading items data...</div>';

        Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            complete: function(results) {
                if (results.errors.length > 0) {
                    console.error('CSV parsing errors:', results.errors);
                    itemsContainer.innerHTML = `<div class="no-results">Error parsing CSV: ${results.errors[0].message}</div>`;
                    excelFileInput.value = '';
                    return;
                }

                const fileInfo = {
                    name: file.name,
                    id: generateUniqueId(),
                    count: results.data.length
                };
                loadedFiles.push(fileInfo);

                const processedData = processCSVData(results.data, fileInfo.id);
                leagueItems = [...leagueItems, ...processedData];

                handleFilterAndSort();
                updateRegionFilter(leagueItems);
                updateLoadedFilesList();
                saveStateToLocalStorage();

                excelFileInput.value = '';
            },
            error: function(error) {
                console.error('Error reading CSV file:', error);
                itemsContainer.innerHTML = '<div class="no-results">Error reading the CSV file. Please try again.</div>';
                excelFileInput.value = '';
            }
        });
    }

    function updateLoadedFilesList() {
        loadedFilesList.innerHTML = '';
        const manualItems = leagueItems.filter(item => item.source === 'manual');

        if (loadedFiles.length === 0 && manualItems.length === 0) {
            loadedFilesList.innerHTML = '<li class="no-files">No files loaded</li>';
            return;
        }

        loadedFiles.forEach(file => {
            const li = document.createElement('li');
            li.innerHTML = `
                ${file.name} (${file.count} items)
                <span class="remove-file" data-file-id="${file.id}">×</span>
            `;
            loadedFilesList.appendChild(li);
        });

        if (manualItems.length > 0) {
            const li = document.createElement('li');
            li.innerHTML = `
                Manually Added (${manualItems.length} items)
                <span class="remove-file" data-source="manual">×</span>
            `;
            loadedFilesList.appendChild(li);
        }

        document.querySelectorAll('.remove-file').forEach(btn => {
            btn.addEventListener('click', function() {
                const fileId = this.getAttribute('data-file-id');
                const source = this.getAttribute('data-source');
                let itemsRemoved = false;

                if (fileId) {
                    const initialLength = leagueItems.length;
                    leagueItems = leagueItems.filter(item => item.fileId !== fileId);
                    if (leagueItems.length < initialLength) itemsRemoved = true;
                    loadedFiles = loadedFiles.filter(file => file.id !== fileId);
                } else if (source === 'manual') {
                    const initialLength = leagueItems.length;
                    leagueItems = leagueItems.filter(item => item.source !== 'manual');
                    if (leagueItems.length < initialLength) itemsRemoved = true;
                }

                if (itemsRemoved) {
                    updateLoadedFilesList();
                    handleFilterAndSort();
                    updateRegionFilter(leagueItems);
                    saveStateToLocalStorage();
                }
            });
        });
    }

    function processCSVData(csvData, fileId) {
        return csvData.map((row, index) => {
            return {
                id: `${fileId}-${index}`,
                name: row['Item Name'] || row['name'] || 'Unknown Item',
                region: capitalize(row['Region'] || row['region'] || 'Unknown'),
                lore: row['Lore'] || row['lore'] || '',
                descriptionLore: row['DescriptionLore'] || row['descriptionLore'] || '',
                image: row['ImageURL'] || row['image'] || '',
                fileId: fileId,
                source: 'csv'
            };
        });
    }

    function updateRegionFilter(items) {
        const currentRegion = categoryFilter.value;
        const regions = new Set();
        items.forEach(item => {
            if (item.region) {
                regions.add(item.region);
            }
        });

        const defaultOption = categoryFilter.options[0];
        categoryFilter.innerHTML = '';
        categoryFilter.appendChild(defaultOption);

        Array.from(regions).sort().forEach(region => {
            const option = document.createElement('option');
            option.value = region;
            option.textContent = region;
            categoryFilter.appendChild(option);
        });

        if (Array.from(regions).includes(currentRegion)) {
            categoryFilter.value = currentRegion;
        }
    }

    function displayItems(items) {
        itemsContainer.innerHTML = '';

        if (items.length === 0 && leagueItems.length > 0) {
            itemsContainer.innerHTML = '<div class="no-results">No items match your search/filter</div>';
            return;
        } else if (items.length === 0 && leagueItems.length === 0) {
            if (!localStorage.getItem(LOCAL_STORAGE_KEY)) {
                itemsContainer.innerHTML = '<div class="initial-message">Upload a CSV or add items manually</div>';
            } else {
                itemsContainer.innerHTML = '<div class="no-results">No items found</div>';
            }
            return;
        }

        items.forEach(item => {
            const itemCard = document.createElement('div');
            itemCard.className = 'item-card';
            itemCard.dataset.id = item.id;

            itemCard.innerHTML = `
                <div class="item-image-container">
                    <img class="item-image" src="${item.image || 'placeholder.png'}" alt="${item.name}" onerror="this.onerror=null; this.src='placeholder.png';">
                </div>
                <div class="item-name-container">
                    <div class="item-name">${item.name}</div>
                </div>
                <div class="item-region-container">
                    <div class="item-region">${item.region}</div>
                </div>
            `;

            itemCard.addEventListener('click', () => showItemDetails(item));
            itemsContainer.appendChild(itemCard);
        });
    }

    function filterItems() {
        const searchTerm = searchInput.value.toLowerCase();
        const regionTerm = categoryFilter.value;

        return leagueItems.filter(item => {
            const nameMatch = item.name?.toLowerCase().includes(searchTerm);
            const loreMatch = item.lore?.toLowerCase().includes(searchTerm);
            const descMatch = item.descriptionLore?.toLowerCase().includes(searchTerm);
            const regionMatch = regionTerm === '' || item.region === regionTerm;

            return (nameMatch || loreMatch || descMatch) && regionMatch;
        });
    }

    function showItemDetails(item) {
        currentEditingItem = item;

        modalContent.innerHTML = '';

        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'item-details';

        detailsDiv.innerHTML = `
            <img id="editItemImageDisplay" src="${item.image || 'placeholder.png'}" alt="${item.name}" onerror="this.onerror=null; this.src='placeholder.png';">
            <input type="text" id="editItemImageUrl" class="image-url-input hidden" value="${item.image || ''}" placeholder="Enter image URL...">

            <h2 id="editItemTitle" class="editable-title editable-field" contenteditable="true">${item.name}</h2>

            <div class="detail-section">
                <span class="section-label">Region:</span>
                <div id="editItemRegion" class="item-region editable-field" contenteditable="true" data-placeholder="Enter region...">${item.region || ''}</div>
            </div>

            <div class="detail-section">
                <span class="section-label">Description:</span>
                <div id="editItemDescription" class="item-description-lore editable-field" contenteditable="true" data-placeholder="Enter description...">${item.descriptionLore || ''}</div>
            </div>

            <div class="detail-section">
                <span class="section-label">Lore:</span>
                <div id="editItemLore" class="item-lore editable-field" contenteditable="true" data-placeholder="Enter lore...">${item.lore || ''}</div>
            </div>
        `;
        modalContent.appendChild(detailsDiv);

        const imageUrlInput = modalContent.querySelector('#editItemImageUrl');
        const imageDisplay = modalContent.querySelector('#editItemImageDisplay');

        if (imageUrlInput && imageDisplay) {
            imageDisplay.addEventListener('click', () => {
                imageUrlInput.classList.toggle('hidden');
                if (!imageUrlInput.classList.contains('hidden')) {
                    imageUrlInput.focus();
                    imageUrlInput.select();
                }
            });

            imageUrlInput.addEventListener('input', () => {
                const newSrc = imageUrlInput.value.trim();
                imageDisplay.src = newSrc || 'placeholder.png';
                imageDisplay.onerror = function() { this.onerror=null; this.src='placeholder.png'; };
            });
        } else {
            console.error("Could not find image display or URL input elements in modal.");
        }

        modal.style.display = 'block';
    }

    function exportToCSV() {
        console.log("Exporting CSV...");
        if (leagueItems.length === 0) {
            alert('No items to export!');
            console.log("Export aborted: No items.");
            return;
        }

        try {
            const headers = ['Item Name', 'Region', 'Lore', 'DescriptionLore', 'ImageURL'];

            const csvData = leagueItems.map(item => {
                return {
                    'Item Name': item.name || '',
                    'Region': item.region || '',
                    'Lore': item.lore || '',
                    'DescriptionLore': item.descriptionLore || '',
                    'ImageURL': item.image || ''
                };
            });

            const csv = Papa.unparse(csvData, {
                columns: headers,
                header: true
            });

            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });

            if (typeof saveAs === 'function') {
                saveAs(blob, 'exported_items.csv');
            } else {
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.setAttribute('href', url);
                link.setAttribute('download', 'exported_items.csv');
                link.style.visibility = 'hidden';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
            }
            console.log("CSV export initiated.");

        } catch (error) {
            console.error("Error during CSV export:", error);
            alert("An error occurred during CSV export. Check the console for details.");
        }
    }

    initializeApp();
});
