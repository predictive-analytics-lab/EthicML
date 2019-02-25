"""
Class to describe features of the SQF dataset
"""

from ethicml.data.dataset import Dataset


class Sqf(Dataset):
    """Stop, question and frisk dataset"""
    def __init__(self, split: str = "Sex", discrete_only: bool = False):
        super().__init__()
        self.discrete_only = discrete_only
        self.features = [
            'perstop',
            'sex',
            'race',
            'age',
            'ht_feet',
            'ht_inch',
            'weight',
            'weapon',
            'typeofid_O',
            'typeofid_P',
            'typeofid_R',
            'typeofid_V',
            'explnstp_N',
            'explnstp_Y',
            'othpers_N',
            'othpers_Y',
            'arstmade_N',
            'arstmade_Y',
            'offunif_N',
            'offunif_Y',
            'frisked_N',
            'frisked_Y',
            'searched_N',
            'searched_Y',
            'pf_hands_N',
            'pf_hands_Y',
            'pf_wall_N',
            'pf_wall_Y',
            'pf_grnd_N',
            'pf_grnd_Y',
            'pf_drwep_N',
            'pf_drwep_Y',
            'pf_ptwep_N',
            'pf_ptwep_Y',
            'pf_baton_N',
            'pf_baton_Y',
            'pf_hcuff_N',
            'pf_hcuff_Y',
            'pf_pepsp_N',
            'pf_pepsp_Y',
            'pf_other_N',
            'pf_other_Y',
            'radio_N',
            'radio_Y',
            'ac_rept_N',
            'ac_rept_Y',
            'ac_inves_N',
            'ac_inves_Y',
            'rf_vcrim_N',
            'rf_vcrim_Y',
            'rf_othsw_N',
            'rf_othsw_Y',
            'ac_proxm_N',
            'ac_proxm_Y',
            'rf_attir_N',
            'rf_attir_Y',
            'cs_objcs_N',
            'cs_objcs_Y',
            'cs_descr_N',
            'cs_descr_Y',
            'cs_casng_N',
            'cs_casng_Y',
            'cs_lkout_N',
            'cs_lkout_Y',
            'rf_vcact_N',
            'rf_vcact_Y',
            'cs_cloth_N',
            'cs_cloth_Y',
            'cs_drgtr_N',
            'cs_drgtr_Y',
            'ac_evasv_N',
            'ac_evasv_Y',
            'ac_assoc_N',
            'ac_assoc_Y',
            'cs_furtv_N',
            'cs_furtv_Y',
            'rf_rfcmp_N',
            'rf_rfcmp_Y',
            'ac_cgdir_N',
            'ac_cgdir_Y',
            'rf_verbl_N',
            'rf_verbl_Y',
            'cs_vcrim_N',
            'cs_vcrim_Y',
            'cs_bulge_N',
            'cs_bulge_Y',
            'cs_other_N',
            'cs_other_Y',
            'ac_incid_N',
            'ac_incid_Y',
            'ac_time_N',
            'ac_time_Y',
            'rf_knowl_N',
            'rf_knowl_Y',
            'ac_stsnd_N',
            'ac_stsnd_Y',
            'ac_other_N',
            'ac_other_Y',
            'sb_hdobj_N',
            'sb_hdobj_Y',
            'sb_outln_N',
            'sb_outln_Y',
            'sb_admis_N',
            'sb_admis_Y',
            'sb_other_N',
            'sb_other_Y',
            'rf_furt_N',
            'rf_furt_Y',
            'rf_bulg_N',
            'rf_bulg_Y',
            'offverb_ ',
            'offverb_V',
            'offshld_ ',
            'offshld_S',
            'forceuse_ ',
            'forceuse_DO',
            'forceuse_DS',
            'forceuse_OR',
            'forceuse_OT',
            'forceuse_SF',
            'forceuse_SW',
            'haircolr_BA',
            'haircolr_BK',
            'haircolr_BL',
            'haircolr_BR',
            'haircolr_DY',
            'haircolr_GY',
            'haircolr_RA',
            'haircolr_SN',
            'haircolr_SP',
            'haircolr_XX',
            'haircolr_ZZ',
            'eyecolor_BK',
            'eyecolor_BL',
            'eyecolor_BR',
            'eyecolor_DF',
            'eyecolor_GR',
            'eyecolor_GY',
            'eyecolor_HA',
            'eyecolor_XX',
            'eyecolor_Z',
            'build_H',
            'build_M',
            'build_T',
            'build_U',
            'build_Z'
        ]

        self.continuous_features = [
            'perstop', 'ht_feet', 'age', 'ht_inch', 'perobs', 'weight'
        ]

        if split == "Sex":
            self.sens_attrs = ['sex']
            self.s_prefix = ['sex']
            self.class_labels = ['weapon']
            self.class_label_prefix = ['weapon']
        elif split == "Race":
            self.sens_attrs = ['race']
            self.s_prefix = ['race']
            self.class_labels = ['weapon']
            self.class_label_prefix = ['weapon']
        elif split == "Race-Sex":
            self.sens_attrs = ['sex',
                               'race']
            self.s_prefix = ['race', 'sex']
            self.class_labels = ['weapon']
            self.class_label_prefix = ['weapon']
        else:
            raise NotImplementedError

    @property
    def name(self) -> str:
        return "SQF"

    @property
    def filename(self) -> str:
        return "sqf.csv"