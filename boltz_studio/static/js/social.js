// Social features - stars, forks, comments, collections
let currentDesign = null;
let designModalViewer = null;

// Design Modal
async function showDesignModal(designId) {
    document.getElementById('design-modal').classList.add('visible');

    try {
        const res = await fetch(`/api/designs/${designId}`);
        currentDesign = await res.json();

        // Update modal content
        document.getElementById('design-modal-title').textContent = currentDesign.name;
        document.getElementById('design-modal-author').textContent = `by ${currentDesign.author_name || 'Anonymous'}`;
        document.getElementById('design-modal-date').textContent = formatDate(currentDesign.created_at);
        document.getElementById('design-modal-description').textContent = currentDesign.description || 'No description';

        // Tags
        const tagsContainer = document.getElementById('design-modal-tags');
        tagsContainer.innerHTML = '';
        if (currentDesign.tags && currentDesign.tags.length > 0) {
            currentDesign.tags.forEach(tag => {
                const tagEl = document.createElement('span');
                tagEl.className = 'tag';
                tagEl.textContent = tag;
                tagsContainer.appendChild(tagEl);
            });
        }

        // Metrics
        const plddt = currentDesign.plddt ? (currentDesign.plddt * 100).toFixed(0) + '%' : '-';
        const ptm = currentDesign.ptm ? (currentDesign.ptm * 100).toFixed(0) + '%' : '-';
        document.getElementById('design-modal-plddt').textContent = plddt;
        document.getElementById('design-modal-ptm').textContent = ptm;
        document.getElementById('design-modal-residues').textContent = currentDesign.sequence?.length || '-';

        // Sequence
        document.getElementById('design-modal-sequence').textContent = currentDesign.sequence || '-';

        // Star count and state
        document.getElementById('design-star-count').textContent = currentDesign.star_count || 0;
        updateStarButton(currentDesign.is_starred);

        // Show delete button if user is the owner
        const deleteBtn = document.getElementById('design-delete-btn');
        if (deleteBtn) {
            const isOwner = currentUser && currentDesign.author_id === currentUser.id;
            deleteBtn.style.display = isOwner ? 'inline-flex' : 'none';
        }

        // Load 3D viewer
        loadDesignViewer(currentDesign.pdb_data);

        // Load comments
        loadComments(designId);
    } catch (err) {
        console.error('Failed to load design:', err);
    }
}

function hideDesignModal() {
    document.getElementById('design-modal').classList.remove('visible');
    if (designModalViewer) {
        designModalViewer.clear();
    }
    currentDesign = null;
}

function loadDesignViewer(pdbData) {
    const container = document.getElementById('design-viewer');

    if (designModalViewer) {
        designModalViewer.clear();
    } else {
        designModalViewer = $3Dmol.createViewer(container, {
            backgroundColor: '#c8e6df',
            antialias: true
        });
    }

    if (pdbData) {
        designModalViewer.addModel(pdbData, 'pdb');
        designModalViewer.setStyle({}, { cartoon: { color: '#0d9373' } });
        designModalViewer.zoomTo();
        designModalViewer.render();
    }
}

// Stars
async function toggleStar() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    if (!currentDesign) return;

    try {
        if (currentDesign.is_starred) {
            await fetch(`/api/designs/${currentDesign.id}/star`, { method: 'DELETE' });
            currentDesign.is_starred = false;
            currentDesign.star_count = Math.max(0, (currentDesign.star_count || 1) - 1);
        } else {
            await fetch(`/api/designs/${currentDesign.id}/star`, { method: 'POST' });
            currentDesign.is_starred = true;
            currentDesign.star_count = (currentDesign.star_count || 0) + 1;
        }

        document.getElementById('design-star-count').textContent = currentDesign.star_count;
        updateStarButton(currentDesign.is_starred);
    } catch (err) {
        console.error('Failed to toggle star:', err);
    }
}

function updateStarButton(isStarred) {
    const btn = document.getElementById('design-star-btn');
    if (isStarred) {
        btn.classList.add('starred');
        btn.querySelector('svg').setAttribute('fill', 'currentColor');
    } else {
        btn.classList.remove('starred');
        btn.querySelector('svg').setAttribute('fill', 'none');
    }
}

// Forks
async function forkDesign() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    if (!currentDesign) return;

    const forkName = prompt('Name for your fork:', `Fork of ${currentDesign.name}`);
    if (!forkName) return;

    try {
        const res = await fetch(`/api/designs/${currentDesign.id}/fork`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: forkName })
        });
        const data = await res.json();

        hideDesignModal();

        // Load the forked design into the editor
        document.getElementById('sequence').value = currentDesign.sequence;
        document.getElementById('seq-length').textContent = currentDesign.sequence.length;
        switchTab('predict');

        alert('Design forked! You can now modify and save it as your own.');
    } catch (err) {
        console.error('Failed to fork design:', err);
        alert('Failed to fork design');
    }
}

// Comments
async function loadComments(designId) {
    const container = document.getElementById('comments-list');
    container.innerHTML = '<div class="loading">Loading comments...</div>';

    try {
        const res = await fetch(`/api/designs/${designId}/comments`);
        const data = await res.json();

        container.innerHTML = '';

        if (data.comments && data.comments.length > 0) {
            data.comments.forEach(comment => {
                container.appendChild(createCommentElement(comment));
            });
        } else {
            container.innerHTML = '<div class="empty-state">No comments yet</div>';
        }
    } catch (err) {
        console.error('Failed to load comments:', err);
        container.innerHTML = '<div class="error-state">Failed to load comments</div>';
    }
}

function createCommentElement(comment) {
    const el = document.createElement('div');
    el.className = 'comment';
    el.innerHTML = `
        <div class="comment-header">
            <img src="${comment.author_avatar || ''}" alt="" class="comment-avatar">
            <span class="comment-author">${escapeHtml(comment.author_name || 'Anonymous')}</span>
            <span class="comment-date">${formatDate(comment.created_at)}</span>
            ${comment.lab_validated ? '<span class="lab-badge">Lab Validated</span>' : ''}
        </div>
        <div class="comment-content">${escapeHtml(comment.content)}</div>
    `;
    return el;
}

async function submitComment() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    if (!currentDesign) return;

    const input = document.getElementById('comment-input');
    const content = input.value.trim();

    if (!content) return;

    try {
        await fetch(`/api/designs/${currentDesign.id}/comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });

        input.value = '';
        loadComments(currentDesign.id);
    } catch (err) {
        console.error('Failed to submit comment:', err);
    }
}

// Collections
let collections = [];

async function loadCollections() {
    if (!currentUser) {
        document.getElementById('collections-list').innerHTML = `
            <div class="empty-state">
                <p>Sign in to create and manage collections</p>
                <button class="btn btn-primary" onclick="showLoginModal()">Sign In</button>
            </div>
        `;
        return;
    }

    const container = document.getElementById('collections-list');
    container.innerHTML = '<div class="loading">Loading collections...</div>';

    try {
        const res = await fetch('/api/collections');
        collections = await res.json();

        container.innerHTML = '';

        if (collections.length > 0) {
            collections.forEach(collection => {
                container.appendChild(createCollectionElement(collection));
            });
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No collections yet</p>
                    <button class="btn btn-primary" onclick="showCreateCollectionModal()">Create Collection</button>
                </div>
            `;
        }
    } catch (err) {
        console.error('Failed to load collections:', err);
        container.innerHTML = '<div class="error-state">Failed to load collections</div>';
    }
}

function createCollectionElement(collection) {
    const el = document.createElement('div');
    el.className = 'collection-card';
    el.onclick = () => viewCollection(collection.id);

    el.innerHTML = `
        <div class="collection-info">
            <h3>${escapeHtml(collection.name)}</h3>
            <p>${escapeHtml(collection.description || 'No description')}</p>
            <div class="collection-meta">
                <span>${collection.design_count || 0} designs</span>
                <span>${collection.is_public ? 'Public' : 'Private'}</span>
            </div>
        </div>
    `;

    return el;
}

async function viewCollection(collectionId) {
    // TODO: Implement collection detail view
    console.log('View collection:', collectionId);
}

function showCreateCollectionModal() {
    if (!currentUser) {
        showLoginModal();
        return;
    }
    // TODO: Implement create collection modal
    const name = prompt('Collection name:');
    if (name) {
        createCollection(name);
    }
}

async function createCollection(name, description = '') {
    try {
        await fetch('/api/collections', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description, is_public: true })
        });

        loadCollections();
    } catch (err) {
        console.error('Failed to create collection:', err);
    }
}

async function addToCollection() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    if (!currentDesign) return;

    // Simple implementation - show list of collections
    await loadCollections();

    if (collections.length === 0) {
        const name = prompt('Create a new collection:');
        if (name) {
            await createCollection(name);
            await loadCollections();
        }
    }

    if (collections.length > 0) {
        const options = collections.map((c, i) => `${i + 1}. ${c.name}`).join('\n');
        const choice = prompt(`Add to collection:\n${options}\n\nEnter number:`);
        const index = parseInt(choice) - 1;

        if (index >= 0 && index < collections.length) {
            try {
                await fetch(`/api/collections/${collections[index].id}/designs`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ design_id: currentDesign.id })
                });
                alert('Added to collection!');
            } catch (err) {
                console.error('Failed to add to collection:', err);
            }
        }
    }
}

function copySequence() {
    if (!currentDesign?.sequence) return;

    navigator.clipboard.writeText(currentDesign.sequence).then(() => {
        showToast('Sequence copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// Delete design (owner only)
async function deleteDesign() {
    if (!currentUser || !currentDesign) return;

    // Check ownership
    if (currentDesign.author_id !== currentUser.id) {
        showToast('You can only delete your own designs', 'error');
        return;
    }

    const confirmed = await showConfirm(
        'Delete Design',
        `Are you sure you want to delete "${currentDesign.name}"? This action cannot be undone.`,
        'Delete'
    );

    if (!confirmed) return;

    try {
        const res = await fetch(`/api/designs/${currentDesign.id}`, {
            method: 'DELETE'
        });

        if (res.ok) {
            hideDesignModal();
            showToast('Design deleted successfully');

            // Refresh the current view
            if (currentView === 'mine') {
                loadMyDesigns();
            } else if (currentView === 'starred') {
                loadStarredDesigns();
            } else {
                loadDesigns(currentFilters);
            }
        } else {
            const data = await res.json();
            showToast(data.detail || 'Failed to delete design', 'error');
        }
    } catch (err) {
        console.error('Failed to delete design:', err);
        showToast('Failed to delete design', 'error');
    }
}

// Save Design Modal
function showSaveModal() {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    if (!window.currentPdbData) {
        alert('No structure to save. Run a prediction first.');
        return;
    }

    document.getElementById('save-modal').classList.add('visible');
}

function hideSaveModal() {
    document.getElementById('save-modal').classList.remove('visible');
}

async function saveDesign() {
    const name = document.getElementById('save-name').value.trim();
    const description = document.getElementById('save-description').value.trim();
    const tagsInput = document.getElementById('save-tags').value.split(',').map(t => t.trim()).filter(t => t);
    const isPublic = document.getElementById('save-public').checked;

    if (!name) {
        alert('Please enter a name');
        return;
    }

    // Format tags with default type 'purpose'
    const tags = tagsInput.map(t => ({ tag: t, tag_type: 'purpose' }));

    try {
        const res = await fetch('/api/designs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                description: description || null,
                tags,
                is_public: isPublic,
                sequence: document.getElementById('sequence').value,
                structure_pdb: window.currentPdbData,
                confidence_score: window.currentConfidence?.confidence_score,
                complex_plddt: window.currentConfidence?.complex_plddt ? window.currentConfidence.complex_plddt * 100 : null,
                ptm: window.currentConfidence?.ptm,
                plddt_per_residue: window.plddt || null
            })
        });

        if (res.ok) {
            hideSaveModal();
            alert('Design saved!');
        } else {
            const data = await res.json();
            alert(data.detail || 'Failed to save design');
        }
    } catch (err) {
        console.error('Failed to save design:', err);
        alert('Failed to save design');
    }
}
