from plantera.service import add_plant_species

def create_species(plant_id: int = 1) -> bool|Exception:
    """
    Parameters
    ----------
    plant_id : int, optional
        1 for Crassula (default), 2 for Rosa.

    Returns
    -------
    bool
        True on success, False if plant_id is invalid.
    """
    if plant_id == 1:
        return add_plant_species(
            "Crassula",
            "Jade Plant",
            "Soak when soil is completely dry for a day or two",
        )
    elif plant_id == 2:
        return add_plant_species(
            "Rosa",
            "Rose",
            "Water deeply at the base 2-3 times per week in warm weather, once a week in cooler weather.",
        )
    else:
        return False