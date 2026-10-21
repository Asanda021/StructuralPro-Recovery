"""A joint reviewer cannot be a preparer or approver of either physical member.

Synthetic fixture only. Even a successful audit must keep BOQ/commit blocked.
"""
from copy import deepcopy
import pytest

from core.takeoff.bored_pile_joint_crosswalk import OwnershipError, _digest
from test_bored_pile_joint_crosswalk import fixture, check


@pytest.mark.parametrize('actor', [
    'ownership_preparer', 'pile_source_approver', 'cap_source_approver',
    'cap_geometry_approver', 'cap_bar_approver', 'column_source_approver',
])
def test_joint_reviewer_must_be_independent_of_both_members(actor):
    parts = list(fixture())
    value = 'SameReviewer'
    joint, project = parts[3], parts[4]
    joint['reviewer'] = value
    if actor == 'ownership_preparer':
        parts[2]['prepared_by'] = value
    elif actor == 'pile_source_approver':
        parts[0]['source']['approved_by'] = value
    else:
        target = 'COLUMN' if actor == 'column_source_approver' else 'CAP'
        record = project['reviewed_structural_members'][target]
        if actor.endswith('source_approver'):
            record['data']['source'] = {'approved_by': value}
        elif actor == 'cap_geometry_approver':
            record['data']['geometry']['approved_by'] = value
        elif actor == 'cap_bar_approver':
            record['data']['rebars']['starters']['series'][0]['approved_by'] = value
        counterpart_link = next(link for link in joint['interfaces']
                                if link['other_member_id'] == record['data']['member_id'])
        counterpart_link['other_record_sha256'] = _digest(record)
    with pytest.raises(OwnershipError, match='بازبین.*مستقل'):
        check(*parts)


def test_distinct_reviewers_do_not_grant_financial_approval():
    parts = fixture()
    result = check(*parts)
    assert result['status'] == 'JOINT_CROSSWALK_PREVIEW_ONLY'
    assert result['rows'] == []
    assert result['ready_for_boq'] is False
    assert result['commit_allowed'] is False
