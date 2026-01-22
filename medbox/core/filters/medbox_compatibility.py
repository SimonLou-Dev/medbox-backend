"""Filters for medications compatible with MedBox 1 (5cm x 5cm x 5cm)."""

# Pharmaceutical forms compatible with MedBox 1 (5cm x 5cm x 5cm)
MEDBOX_1_COMPATIBLE_FORMS = {
    # Tablets and capsules
    "comprimé",
    "comprimé dispersible",
    "comprimé dispersible et orodispersible",
    "comprimé dispersible ou à croquer",
    "comprimé dispersible sécable",
    "comprimé effervescent",
    "comprimé effervescent(e)",
    "comprimé effervescent(e) sécable",
    "comprimé enrobé",
    "comprimé enrobé gastro-résistant",
    "comprimé enrobé gastro-résistant(e)",
    "comprimé enrobé sécable",
    "comprimé enrobé à croquer",
    "comprimé enrobé à libération prolongée",
    "comprimé gastro-résistant",
    "comprimé gastro-résistant(e)",
    "comprimé muco-adhésif",
    "comprimé orodispersible",
    "comprimé orodispersible sécable",
    "comprimé osmotique",
    "comprimé pelliculé",
    "comprimé pelliculé dispersible",
    "comprimé pelliculé gastro-résistant",
    "comprimé pelliculé gastro-résistant(e)",
    "comprimé pelliculé quadrisécable",
    "comprimé pelliculé sécable",
    "comprimé pelliculé sécable à libération prolongée",
    "comprimé pelliculé à libération modifiée",
    "comprimé pelliculé à libération prolongée",
    "comprimé pour solution buvable",
    "comprimé pour suspension buvable",
    "comprimé quadrisécable",
    "comprimé sécable",
    "comprimé sécable pelliculé",
    "comprimé sécable pour suspension buvable",
    "comprimé sécable à libération modifiée",
    "comprimé sécable à libération prolongée",
    "comprimé à croquer",
    "comprimé à croquer ou à sucer",
    "comprimé à croquer à sucer ou dispersible",
    "comprimé à libération modifiée",
    "comprimé à libération modifiée sécable",
    "comprimé à libération prolongée",
    "comprimé à sucer",
    "comprimé à sucer ou à croquer",
    "comprimé à sucer sécable",
    # Capsules
    "capsule",
    "capsule molle",
    "capsule pour inhalation par vapeur",
    "gélule",
    "gélule gastro-résistant",
    "gélule gastro-résistant(e)",
    "gélule à libération modifiée",
    "gélule à libération prolongée",
    "poudre en gélule",
    "granulés en gélule",
    # Granules
    "granules",
    "granules à libération prolongée",
    "granulés",
    "granulés effervescent",
    "granulés effervescent(e) pour solution buvable",
    "granulés enrobé",
    "granulés enrobé en vrac",
    "granulés gastro-résistant",
    "granulés gastro-résistant(e)",
    "granulés gastro-résistant(e) pour suspension buvable",
    "granulés orodispersible",
    "granulés pour solution buvable",
    "granulés pour suspension buvable",
    "granulés à croquer",
    "granulés à libération prolongée",
    # Powders and solutions (small volumes)
    "poudre",
    "poudre buvable",
    "poudre effervescent",
    "poudre effervescent(e) pour solution buvable",
    "poudre effervescent(e) pour suspension buvable",
    "poudre pour inhalation",
    "poudre pour inhalation en gélule",
    "poudre pour solution buvable",
    "poudre pour suspension buvable",
    "collutoire",
    "lotion",
    # Patches and films
    "patch",
    "film orodispersible",
    # Others
    "pastille",
    "pastille à sucer",
}


def is_medbox_1_compatible(pharmaceutical_form: str) -> bool:
    """Check if pharmaceutical form is compatible with MedBox 1 (5cm x 5cm x 5cm).

    Args:
        pharmaceutical_form: The pharmaceutical form string from the API

    Returns:
        bool: True if the form is compatible, False otherwise

    """
    if not pharmaceutical_form:
        return False

    # Normalize the form (lowercase and strip whitespace)
    form_normalized = pharmaceutical_form.lower().strip()

    # Check if the form is in the compatible list
    if form_normalized in MEDBOX_1_COMPATIBLE_FORMS:
        return True

    # Check for partial matches (for forms with variations)
    # This handles cases like "comprimé et comprimé" or "solution et solution"
    for compatible_form in MEDBOX_1_COMPATIBLE_FORMS:
        if compatible_form in form_normalized:
            # Only match if it's a primary form component, not a complex combination
            parts = form_normalized.split(" et ")
            if parts and parts[0].strip() == compatible_form:
                return True

    return False


def get_compatible_forms_count() -> int:
    """Get the number of compatible pharmaceutical forms.

    Returns:
        int: Number of compatible forms

    """
    return len(MEDBOX_1_COMPATIBLE_FORMS)
