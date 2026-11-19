"""Search-engine helpers: the landing FAQ and JSON-LD structured data.

JSON-LD is built here as plain dicts and rendered by base.html with `tojson`, so
the markup Google reads always matches what the page shows. Absolute URLs come
from PUBLIC_BASE_URL only (never the request host); with it unset the `url`
fields are left out.
"""

COURSE_NAME = "La Queta - Free Catalan for complete beginners"
SITE_NAME = "La Queta"


def landing_faq(lesson_count: int) -> list[dict]:
    """The FAQ on /; also the source for its FAQPage JSON-LD.

    Only state things that are true of this app: no invented hours or counts.
    """
    return [
        {
            "question": "Is it free?",
            "answer": "Yes. Every lesson, every test and every vocab deck is free.",
        },
        {
            "question": "Do I need an account?",
            "answer": (
                "Not to start. You can read any lesson and take its test without one. "
                "A free account saves the lessons you finish and gives you the vocab "
                "flashcards and a daily vocab review."
            ),
        },
        {
            "question": "Is this Central Catalan?",
            "answer": (
                "Yes. The lessons teach standard Central Catalan, "
                "the variety spoken in Barcelona."
            ),
        },
        {
            "question": "How long does A1 take?",
            "answer": (
                "It depends on your pace, and there is no deadline. "
                f"The course is {lesson_count} lessons, and you can take them in any order."
            ),
        },
        {
            "question": "What comes after A1?",
            "answer": (
                "A2 is not here yet. Once you finish A1, keep reviewing your vocab "
                "every day so the words stay fresh."
            ),
        },
    ]


def _base(base_url: str) -> str:
    return (base_url or "").rstrip("/")


def _provider(base_url: str) -> dict:
    org = {"@type": "Organization", "name": SITE_NAME}
    if _base(base_url):
        org["url"] = _base(base_url) + "/"
    return org


def course_json_ld(base_url: str, description: str, level_code: str) -> dict:
    """`Course` for the home page: free, online, taught in English, teaching Catalan."""
    data = {
        "@context": "https://schema.org",
        "@type": "Course",
        "name": COURSE_NAME,
        "description": description,
        "provider": _provider(base_url),
        "inLanguage": "en",
        "teaches": "Catalan",
        "about": {"@type": "Language", "name": "Catalan", "alternateName": "ca"},
        "educationalLevel": level_code,
        "isAccessibleForFree": True,
        "offers": {
            "@type": "Offer",
            "category": "Free",
            "price": 0,
            "priceCurrency": "EUR",
        },
        "hasCourseInstance": {"@type": "CourseInstance", "courseMode": "Online"},
    }
    if _base(base_url):
        data["url"] = _base(base_url) + "/"
    return data


def faq_json_ld(faq: list[dict]) -> dict:
    """`FAQPage` built from the same entries the page renders."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
            }
            for item in faq
        ],
    }


def lesson_json_ld(
    base_url: str, lesson: dict, description: str, level_code: str, path: str
) -> dict:
    """`LearningResource` for one lesson, part of the course on the home page."""
    course = {"@type": "Course", "name": COURSE_NAME, "provider": _provider(base_url)}
    if _base(base_url):
        course["url"] = _base(base_url) + "/"
    data = {
        "@context": "https://schema.org",
        "@type": "LearningResource",
        "name": lesson["title"],
        "description": description,
        "learningResourceType": "Lesson",
        "inLanguage": "en",
        "teaches": lesson["summary"],
        "about": {"@type": "Language", "name": "Catalan", "alternateName": "ca"},
        "educationalLevel": level_code,
        "isAccessibleForFree": True,
        "position": lesson["sort_order"],
        "provider": _provider(base_url),
        "isPartOf": course,
    }
    if _base(base_url):
        data["url"] = _base(base_url) + path
    return data
