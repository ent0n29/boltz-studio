"""Tests for Phase B features (Social/Community features)."""

import pytest


class TestReputationStore:
    """Tests for reputation and badges system."""

    @pytest.fixture
    def reputation_store(self, setup_test_db):
        """Create a reputation store for testing."""
        from boltz_studio.services.database import init_db
        from boltz_studio.services.reputation_store import ReputationStore

        init_db()
        return ReputationStore()

    def test_get_all_badges(self, reputation_store):
        """Test retrieving all badge definitions."""
        badges = reputation_store.get_all_badges()

        assert badges.total > 0
        assert len(badges.badges) > 0

        # Check badge structure
        badge = badges.badges[0]
        assert badge.id
        assert badge.slug
        assert badge.name
        assert badge.description
        assert badge.category in ("contribution", "social", "engagement", "verification")

    def test_get_user_badges_empty(self, reputation_store):
        """Test getting badges for user with no badges."""
        badges = reputation_store.get_user_badges("nonexistent_user")

        assert badges.total == 0
        assert len(badges.badges) == 0


class TestValidationStore:
    """Tests for lab validation system."""

    @pytest.fixture
    def validation_store(self, setup_test_db):
        """Create a validation store for testing."""
        from boltz_studio.services.database import init_db
        from boltz_studio.services.validation_store import ValidationStore

        init_db()
        return ValidationStore()

    def test_get_validation_summary_empty(self, validation_store):
        """Test getting validation summary for design with no validations."""
        summary = validation_store.get_summary("nonexistent_design")

        assert summary.total == 0
        assert summary.confirmed == 0
        assert summary.is_validated is False


class TestAPIKeyStore:
    """Tests for API key management."""

    @pytest.fixture
    def api_key_store(self, setup_test_db):
        """Create an API key store for testing."""
        from boltz_studio.services.database import init_db
        from boltz_studio.services.api_key_store import APIKeyStore

        init_db()
        return APIKeyStore()

    @pytest.fixture
    def test_user(self, setup_test_db):
        """Create a test user."""
        from boltz_studio.services.database import get_connection, init_db
        import uuid

        init_db()
        user_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (id, provider, provider_user_id, email, display_name)
                VALUES (?, 'test', ?, 'test@example.com', 'Test User')
                """,
                (user_id, user_id),
            )

        return user_id

    def test_create_api_key(self, api_key_store, test_user):
        """Test creating an API key."""
        from boltz_studio.models.api_key import APIKeyCreate

        data = APIKeyCreate(name="Test Key", scopes="read")
        result = api_key_store.create(test_user, data)

        assert result.id
        assert result.name == "Test Key"
        assert result.key.startswith("bsk_")
        assert result.scopes == "read"

    def test_list_user_keys(self, api_key_store, test_user):
        """Test listing user's API keys."""
        from boltz_studio.models.api_key import APIKeyCreate

        # Create a key
        data = APIKeyCreate(name="Test Key")
        api_key_store.create(test_user, data)

        # List keys
        keys = api_key_store.list_user_keys(test_user)

        assert keys.total == 1
        assert keys.keys[0].name == "Test Key"
        # Full key should not be in list response
        assert not hasattr(keys.keys[0], "key") or keys.keys[0].key_prefix

    def test_validate_key(self, api_key_store, test_user):
        """Test validating an API key."""
        from boltz_studio.models.api_key import APIKeyCreate

        # Create a key
        data = APIKeyCreate(name="Test Key", scopes="read,write")
        created = api_key_store.create(test_user, data)

        # Validate it
        result = api_key_store.validate_key(created.key)

        assert result is not None
        user_id, scopes = result
        assert user_id == test_user
        assert scopes == "read,write"

    def test_validate_invalid_key(self, api_key_store):
        """Test validating an invalid API key."""
        result = api_key_store.validate_key("bsk_invalid_key_12345")
        assert result is None

    def test_delete_api_key(self, api_key_store, test_user):
        """Test deleting an API key."""
        from boltz_studio.models.api_key import APIKeyCreate

        # Create a key
        data = APIKeyCreate(name="Test Key")
        created = api_key_store.create(test_user, data)

        # Delete it
        result = api_key_store.delete(created.id, test_user)
        assert result is True

        # Verify it's gone
        keys = api_key_store.list_user_keys(test_user)
        assert keys.total == 0


class TestActivityStore:
    """Tests for activity feed."""

    @pytest.fixture
    def activity_store(self, setup_test_db):
        """Create an activity store for testing."""
        from boltz_studio.services.database import init_db
        from boltz_studio.services.activity_store import ActivityStore

        init_db()
        return ActivityStore()

    @pytest.fixture
    def test_user(self, setup_test_db):
        """Create a test user."""
        from boltz_studio.services.database import get_connection, init_db
        import uuid

        init_db()
        user_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (id, provider, provider_user_id, email, display_name)
                VALUES (?, 'test', ?, 'test@example.com', 'Test User')
                """,
                (user_id, user_id),
            )

        return user_id

    def test_record_activity(self, activity_store, test_user):
        """Test recording an activity."""
        activity_id = activity_store.record(
            user_id=test_user,
            activity_type="design_published",
            target_type="design",
            target_id="design_123",
        )

        assert activity_id

    def test_get_user_activities(self, activity_store, test_user):
        """Test getting user's activities."""
        # Record some activities
        activity_store.record(
            user_id=test_user,
            activity_type="design_published",
            target_type="design",
            target_id="design_1",
        )
        activity_store.record(
            user_id=test_user,
            activity_type="design_starred",
            target_type="design",
            target_id="design_2",
        )

        # Get activities
        feed = activity_store.get_user_activities(test_user)

        assert feed.total == 2
        assert len(feed.activities) == 2


class TestOrgStore:
    """Tests for organizations."""

    @pytest.fixture
    def org_store(self, setup_test_db):
        """Create an org store for testing."""
        from boltz_studio.services.database import init_db
        from boltz_studio.services.org_store import OrgStore

        init_db()
        return OrgStore()

    @pytest.fixture
    def test_user(self, setup_test_db):
        """Create a test user."""
        from boltz_studio.services.database import get_connection, init_db
        import uuid

        init_db()
        user_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (id, provider, provider_user_id, email, display_name)
                VALUES (?, 'test', ?, 'test@example.com', 'Test User')
                """,
                (user_id, user_id),
            )

        return user_id

    def test_create_organization(self, org_store, test_user):
        """Test creating an organization."""
        import uuid
        from boltz_studio.models.organization import OrganizationCreate

        slug = f"test-org-{uuid.uuid4().hex[:8]}"
        data = OrganizationCreate(
            slug=slug,
            name="Test Organization",
            description="A test organization",
        )
        org_id = org_store.create(test_user, data)

        assert org_id

        # Verify org exists
        org = org_store.get_by_slug(slug)
        assert org is not None
        assert org.name == "Test Organization"
        assert org.member_count == 1  # Creator is member

    def test_create_duplicate_slug(self, org_store, test_user):
        """Test creating organization with duplicate slug fails."""
        import uuid
        from boltz_studio.models.organization import OrganizationCreate

        slug = f"test-org-dup-{uuid.uuid4().hex[:8]}"
        data = OrganizationCreate(slug=slug, name="Test Org")
        org_store.create(test_user, data)

        # Try to create another with same slug
        with pytest.raises(ValueError, match="already taken"):
            org_store.create(test_user, data)

    def test_get_user_role(self, org_store, test_user):
        """Test getting user's role in organization."""
        import uuid
        from boltz_studio.models.organization import OrganizationCreate

        slug = f"test-org-role-{uuid.uuid4().hex[:8]}"
        data = OrganizationCreate(slug=slug, name="Test Org")
        org_id = org_store.create(test_user, data)

        role = org_store.get_user_role(org_id, test_user)
        assert role == "owner"


class TestCitation:
    """Tests for citation generation."""

    def test_generate_bibtex(self):
        """Test generating BibTeX citation."""
        from datetime import datetime
        from boltz_studio.services.citation import generate_citation

        citation = generate_citation(
            design_id="test-123",
            design_name="My Protein Design",
            author_name="John Doe",
            created_at=datetime(2025, 1, 15),
            format="bibtex",
        )

        assert "@misc{" in citation
        assert "John Doe" in citation
        assert "My Protein Design" in citation
        assert "2025" in citation

    def test_generate_apa(self):
        """Test generating APA citation."""
        from datetime import datetime
        from boltz_studio.services.citation import generate_citation

        citation = generate_citation(
            design_id="test-123",
            design_name="My Protein Design",
            author_name="John Doe",
            created_at=datetime(2025, 1, 15),
            format="apa",
        )

        assert "John Doe" in citation
        assert "2025" in citation
        assert "Boltz Studio" in citation

    def test_generate_doi_placeholder(self):
        """Test generating DOI placeholder."""
        from boltz_studio.services.citation import generate_doi_placeholder

        doi = generate_doi_placeholder("abc12345-6789-0123-4567-890123456789")

        assert doi.startswith("10.boltz/")
        assert len(doi) > 10


class TestRoutes:
    """Tests for Phase B API routes."""

    def test_get_badges(self, client):
        """Test getting all badges."""
        response = client.get("/api/reputation/badges")

        assert response.status_code == 200
        data = response.json()
        assert "badges" in data
        assert "total" in data
        assert data["total"] > 0

    def test_get_reputation_leaderboard(self, client):
        """Test getting reputation leaderboard."""
        response = client.get("/api/reputation/leaderboard")

        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data

    def test_get_organizations_list(self, client):
        """Test listing organizations."""
        response = client.get("/api/organizations")

        assert response.status_code == 200
        assert isinstance(response.json(), list)
