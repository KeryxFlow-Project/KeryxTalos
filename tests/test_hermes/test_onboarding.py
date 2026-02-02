"""Tests for onboarding wizard."""


from keryxflow.hermes.onboarding import OnboardingWizard, QuickSetupWizard, UserProfile


class TestUserProfile:
    """Tests for UserProfile dataclass."""

    def test_create_beginner_profile(self):
        """Test creating a beginner profile."""
        profile = UserProfile(
            experience_level="beginner",
            risk_profile="conservative",
            show_technical=False,
        )

        assert profile.experience_level == "beginner"
        assert profile.risk_profile == "conservative"
        assert not profile.show_technical

    def test_create_intermediate_profile(self):
        """Test creating an intermediate profile."""
        profile = UserProfile(
            experience_level="intermediate",
            risk_profile="balanced",
            show_technical=False,
        )

        assert profile.experience_level == "intermediate"
        assert profile.risk_profile == "balanced"

    def test_create_advanced_profile(self):
        """Test creating an advanced profile."""
        profile = UserProfile(
            experience_level="advanced",
            risk_profile="aggressive",
            show_technical=True,
        )

        assert profile.experience_level == "advanced"
        assert profile.risk_profile == "aggressive"
        assert profile.show_technical


class TestOnboardingWizard:
    """Tests for OnboardingWizard."""

    def test_init_defaults(self):
        """Test OnboardingWizard initializes with defaults."""
        wizard = OnboardingWizard()
        assert wizard._step == 0
        assert wizard._experience is None
        assert wizard._risk_profile is None

    def test_step_progression(self):
        """Test step progression logic."""
        wizard = OnboardingWizard()

        # Step 0: Welcome
        assert wizard._step == 0

        # Simulate going to step 1
        wizard._step = 1
        assert wizard._step == 1

        # Simulate going to step 2
        wizard._step = 2
        assert wizard._step == 2

        # Simulate going to step 3 (summary)
        wizard._step = 3
        assert wizard._step == 3

    def test_experience_selection(self):
        """Test experience level selection."""
        wizard = OnboardingWizard()

        # Test beginner selection
        wizard._experience = "beginner"
        assert wizard._experience == "beginner"

        # Test intermediate selection
        wizard._experience = "intermediate"
        assert wizard._experience == "intermediate"

        # Test advanced selection
        wizard._experience = "advanced"
        assert wizard._experience == "advanced"

    def test_risk_profile_selection(self):
        """Test risk profile selection."""
        wizard = OnboardingWizard()

        # Test conservative selection
        wizard._risk_profile = "conservative"
        assert wizard._risk_profile == "conservative"

        # Test balanced selection
        wizard._risk_profile = "balanced"
        assert wizard._risk_profile == "balanced"

        # Test aggressive selection
        wizard._risk_profile = "aggressive"
        assert wizard._risk_profile == "aggressive"

    def test_action_select_experience(self):
        """Test action methods for experience selection."""
        wizard = OnboardingWizard()
        wizard._step = 1

        wizard.action_select_1()
        assert wizard._experience == "beginner"

        wizard.action_select_2()
        assert wizard._experience == "intermediate"

        wizard.action_select_3()
        assert wizard._experience == "advanced"

    def test_action_select_risk(self):
        """Test action methods for risk selection."""
        wizard = OnboardingWizard()
        wizard._step = 2

        wizard.action_select_1()
        assert wizard._risk_profile == "conservative"

        wizard.action_select_2()
        assert wizard._risk_profile == "balanced"

        wizard.action_select_3()
        assert wizard._risk_profile == "aggressive"


class TestQuickSetupWizard:
    """Tests for QuickSetupWizard."""

    def test_init(self):
        """Test QuickSetupWizard initialization."""
        wizard = QuickSetupWizard()
        # Just verify it can be instantiated
        assert wizard is not None
