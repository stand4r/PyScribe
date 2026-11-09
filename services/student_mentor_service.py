"""PyScribe services/student_mentor_service.py: Backward-compatibility facade for CodeIntelligenceService."""
from services.code_intelligence_service import CodeIntelligenceService

# Alias for backward compatibility
StudentMentorService = CodeIntelligenceService
