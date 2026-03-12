from .pap import Person

class Maskingeffects:
    # TODO: What should these values be?
    MASK_EFFECTIVENESS = {
        'source_control' : 0.7,
        'wearer_protection': 0.5,
        'both_masked' : 0.85
    }

    @staticmethod
    def calculate_mask_transmission_modifier(infector: Person, susceptible: Person) -> float:
        base_modifier = 1.0
        infector_masked = infector.is_masked()
        susceptible_masked = susceptible.is_masked()

        if infector_masked and susceptible_masked:
            base_modifier *= (1 - Maskingeffects.MASK_EFFECTIVENESS['both_masked'])
        elif infector_masked:
            base_modifier *= (1 - Maskingeffects.MASK_EFFECTIVENESS['source_control'])
        elif susceptible_masked:
            base_modifier *= (1 - Maskingeffects.MASK_EFFECTIVENESS['wearer_protection'])
        return base_modifier

    @staticmethod
    def update_mask_effectiveness(source_control=None, wearer_protection=None, both_masked=None):
        """Allow dynamic updating of mask effectiveness values"""
        if source_control is not None:
            Maskingeffects.MASK_EFFECTIVENESS['source_control'] = source_control
        if wearer_protection is not None:
            Maskingeffects.MASK_EFFECTIVENESS['wearer_protection'] = wearer_protection
        if both_masked is not None:
            Maskingeffects.MASK_EFFECTIVENESS['both_masked'] = both_masked
