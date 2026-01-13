// Social features - collections
// Note: Design viewing, stars, forks, and comments are now handled
// by the page-based design detail view in app.js

// Design Modal - navigates to full page view
function showDesignModal(designId) {
    navigateTo('/community/' + designId);
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

// Add design to collection (takes designId as parameter)
async function addToCollection(designId) {
    if (!currentUser) {
        showLoginModal();
        return;
    }

    if (!designId) return;

    // Load collections first
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
                    body: JSON.stringify({ design_id: designId })
                });
                showToast('Added to collection!');
            } catch (err) {
                console.error('Failed to add to collection:', err);
            }
        }
    }
}
