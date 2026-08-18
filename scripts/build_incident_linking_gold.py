import asyncio
import json
from itertools import combinations
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from civicproof.db.models.incident import Incident
from civicproof.db.models.incident_cluster import IncidentClusterMember
from civicproof.db.session import async_session, close_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FOLDER = PROJECT_ROOT / 'data'
GOLD_PATH = DATA_FOLDER / 'incident_linking_gold.json'
REVIEWS_PATH = DATA_FOLDER / 'incident_linking_cluster_reviews.json'

CLUSTER_REVIEWS = {
    141: {
        'decision': 'correct',
        'event_groups': [[583, 161]],
        'excluded_incidents': [],
        'notes': 'Same blocked-driveway condition at identical coordinates within 56 minutes.'
    },
    266: {
        'decision': 'incorrect',
        'event_groups': [[785], [448], [1053]],
        'excluded_incidents': [],
        'notes': 'Pests, ventilation, and a street cave-in are unrelated complaints merged by the unknown category.'
    },
    369: {
        'decision': 'mostly_correct',
        'event_groups': [[343, 350, 438, 435, 293]],
        'excluded_incidents': [605],
        'notes': 'Five reports describe the same loud party. The vehicle-music report is plausible but not provable from the sparse payload.'
    },
    838: {
        'decision': 'mixed',
        'event_groups': [[756], [1406, 1404]],
        'excluded_incidents': [],
        'notes': 'Two reports share an exact catch-basin location and two-hour window. The earlier report is 32 metres and 22 hours away.'
    },
    842: {
        'decision': 'correct',
        'event_groups': [[1219, 3135]],
        'excluded_incidents': [],
        'notes': 'Persistent pothole reported at identical coordinates about 60 hours apart.'
    },
    855: {
        'decision': 'correct',
        'event_groups': [[990, 1408, 1388]],
        'excluded_incidents': [],
        'notes': 'Construction blockage at identical coordinates over one continuous day.'
    },
    908: {
        'decision': 'correct',
        'event_groups': [[768, 845, 3115]],
        'excluded_incidents': [],
        'notes': 'Persistent pothole at identical coordinates, including two reports within 30 minutes.'
    },
    916: {
        'decision': 'ambiguous',
        'event_groups': [],
        'excluded_incidents': [1286, 1256],
        'notes': 'Reports are simultaneous but 22 metres apart; the source contains no address or narrative identifying one pothole.'
    },
    1052: {
        'decision': 'correct',
        'event_groups': [[1331, 3599]],
        'excluded_incidents': [],
        'notes': 'Persistent pothole at identical coordinates within the configured 72-hour window.'
    },
    1219: {
        'decision': 'correct',
        'event_groups': [[3082, 3186]],
        'excluded_incidents': [],
        'notes': 'Construction blockage at identical coordinates over one continuous day.'
    },
    1259: {
        'decision': 'mixed',
        'event_groups': [[3121, 3099], [3036]],
        'excluded_incidents': [],
        'notes': 'First two cave-ins are five metres and 28 minutes apart. The third is 41 metres away and is treated as a separate road defect.'
    },
    1337: {
        'decision': 'incorrect',
        'event_groups': [[3183], [3182], [3204]],
        'excluded_incidents': [],
        'notes': 'Three separate catch-basin locations spanning 90 to 184 metres were merged because their generic descriptions match.'
    },
    1508: {
        'decision': 'incorrect',
        'event_groups': [[3488], [3548], [3445]],
        'excluded_incidents': [],
        'notes': 'Separate catch-basin locations more than 220 metres apart should remain independent work items.'
    },
    1606: {
        'decision': 'correct',
        'event_groups': [[3342, 3341, 3461, 3500]],
        'excluded_incidents': [],
        'notes': 'Four catch-basin reports share the same point or are within 13 metres during a three-hour window.'
    },
    1621: {
        'decision': 'incorrect',
        'event_groups': [[3414], [3375], [3440]],
        'excluded_incidents': [],
        'notes': 'Separate catch-basin locations 227 to 251 metres apart were merged by identical generic descriptors.'
    },
    2033: {
        'decision': 'incorrect',
        'event_groups': [[3884], [4248]],
        'excluded_incidents': [],
        'notes': 'Construction reports are 58 metres and almost 18 hours apart with no shared address evidence.'
    },
    2180: {
        'decision': 'mostly_correct',
        'event_groups': [[4294, 4118, 4285]],
        'excluded_incidents': [4320],
        'notes': 'Three cave-in reports share exact coordinates. A fourth report 19 metres away is plausible but not provable.'
    },
    2259: {
        'decision': 'correct',
        'event_groups': [[4514, 4450]],
        'excluded_incidents': [],
        'notes': 'Same overgrown branches blocking the street at identical coordinates within 44 minutes.'
    },
    2369: {
        'decision': 'correct',
        'event_groups': [[4158, 4240, 4273, 4309]],
        'excluded_incidents': [],
        'notes': 'Four pothole records have identical coordinates and timestamps and are clear duplicate submissions.'
    },
    2376: {
        'decision': 'mostly_correct',
        'event_groups': [[4236, 4269, 4186, 4219]],
        'excluded_incidents': [4290],
        'notes': 'Four cave-in reports are at the same point within four hours. The fifth is 32 metres away and remains ambiguous.'
    },
    2386: {
        'decision': 'mostly_correct',
        'event_groups': [[4567, 4501, 4497]],
        'excluded_incidents': [5025],
        'notes': 'Three fallen-limb reports are within 19 metres and two hours. A report the following day is not confidently the same limb.'
    },
    2559: {
        'decision': 'mixed',
        'event_groups': [[4727, 4908, 4909], [4845]],
        'excluded_incidents': [],
        'notes': 'Three fallen-tree reports are within six metres. The fourth is 84 metres away and is a different tree.'
    },
    2563: {
        'decision': 'mixed',
        'event_groups': [[4721, 4667, 4670], [4944]],
        'excluded_incidents': [],
        'notes': 'Three fallen-limb reports share exact coordinates. An entire-tree report 66 metres away is a separate tree.'
    },
    2568: {
        'decision': 'mixed',
        'event_groups': [[4609, 4895, 4906, 4649], [4962]],
        'excluded_incidents': [],
        'notes': 'Four tree reports are at one point or within 12 metres. A fallen limb 85 metres away is a separate tree.'
    },
    2657: {
        'decision': 'correct',
        'event_groups': [[4720, 4725, 4657, 5024]],
        'excluded_incidents': [],
        'notes': 'Four reports describe a damaged tree at the same point or within five metres on the same day.'
    }
}

CROSS_CLUSTER_PAIRS = [
    (4828, 4956, True, 'Same tree location and progression from cracked branch to fallen limb.'),
    (4709, 4956, True, 'Same tree location and progression from cracked branch to fallen limb.'),
    (4828, 4967, True, 'Reports are one metre apart and describe the same tree failure.'),
    (4709, 4967, True, 'Reports are one metre apart and describe the same tree failure.'),
    (4134, 4158, True, 'Identical pothole coordinates and timestamp across two generated clusters.'),
    (4134, 4240, True, 'Identical pothole coordinates and timestamp across two generated clusters.'),
    (4134, 4273, True, 'Identical pothole coordinates and timestamp across two generated clusters.'),
    (4134, 4309, True, 'Identical pothole coordinates and timestamp across two generated clusters.'),
    (4308, 4158, True, 'Identical pothole coordinates and timestamp across two generated clusters.'),
    (4308, 4240, True, 'Identical pothole coordinates and timestamp across two generated clusters.'),
    (4308, 4273, True, 'Identical pothole coordinates and timestamp across two generated clusters.'),
    (4308, 4309, True, 'Identical pothole coordinates and timestamp across two generated clusters.'),
    (546, 651, True, 'Same loud-party location within two minutes.'),
    (237, 390, True, 'Same loud-party location within three minutes.'),
    (236, 651, True, 'Same loud-party location within four minutes.'),
    (391, 546, True, 'Same loud-party location within four minutes.'),
    (390, 547, True, 'Same loud-party location within four minutes.'),
    (236, 391, True, 'Same loud-party location within five minutes.'),
    (236, 237, True, 'Same loud-party location within five minutes.'),
    (390, 651, True, 'Same loud-party location within five minutes.'),
    (237, 546, True, 'Same loud-party location within six minutes.'),
    (236, 547, True, 'Same loud-party location within six minutes.'),
    (390, 391, True, 'Same loud-party location within six minutes.'),
    (546, 547, True, 'Same loud-party location within seven minutes.'),
    (4460, 4680, False, 'Different tree assets 84 metres apart and reported on different days.'),
    (4398, 4669, False, 'Different tree assets 89 metres apart and reported more than a day apart.'),
    (4493, 4655, False, 'Different tree assets 99 metres apart.'),
    (4433, 4836, False, 'Different fallen limbs 99 metres apart and reported on different days.'),
    (3431, 3618, False, 'Separate catch-basin assets 79 metres apart and reported on different days.'),
    (3388, 3617, False, 'Separate catch-basin assets 82 metres apart and reported on different days.'),
    (3183, 3262, False, 'Separate catch-basin assets 91 metres apart and reported on different days.'),
    (3569, 3618, False, 'Separate catch-basin assets 158 metres apart.'),
    (3281, 3401, False, 'Separate catch-basin assets 158 metres apart.'),
    (3410, 3617, False, 'Separate catch-basin assets 160 metres apart.'),
    (3535, 3642, False, 'Separate catch-basin assets 161 metres apart.'),
    (1256, 1303, False, 'Simultaneous pothole reports 58 metres apart represent different roadway defects.'),
    (4245, 4313, False, 'Simultaneous pothole reports 64 metres apart represent different roadway defects.'),
    (4104, 4106, False, 'Simultaneous pothole reports 65 metres apart represent different roadway defects.'),
    (1256, 1361, False, 'Simultaneous pothole reports 68 metres apart represent different roadway defects.'),
    (1286, 1303, False, 'Simultaneous pothole reports 81 metres apart represent different roadway defects.'),
    (4136, 4311, False, 'Simultaneous pothole reports 87 metres apart represent different roadway defects.'),
    (1286, 1361, False, 'Simultaneous pothole reports 90 metres apart represent different roadway defects.'),
    (1362, 1363, False, 'Potholes 99 metres apart represent different roadway defects.'),
    (1257, 1363, False, 'Potholes 99 metres apart represent different roadway defects.'),
    (1256, 2965, False, 'Simultaneous pothole reports 100 metres apart represent different roadway defects.'),
    (1303, 2965, False, 'Simultaneous pothole reports 100 metres apart represent different roadway defects.'),
    (1361, 2965, False, 'Simultaneous pothole reports 102 metres apart represent different roadway defects.'),
    (3994, 4750, False, 'Construction waste and tree branches are unrelated obstructions.'),
    (119, 3079, False, 'A blocked traffic sign and construction dumpster are unrelated obstructions.'),
    (2976, 3222, False, 'Construction blockages 271 metres and two days apart are separate work zones.'),
    (3883, 4861, False, 'Construction and tree obstruction reports are unrelated.'),
    (4482, 4867, False, 'Tree obstructions 293 metres apart are separate assets.'),
    (789, 948, False, 'Garbage storage and water-supply complaints are unrelated.'),
    (789, 1076, False, 'Garbage storage and building heat complaints are unrelated.'),
    (195, 385, False, 'Blocked driveway and loud-party complaints are unrelated.'),
    (122, 232, False, 'Blocked-hydrant parking and loud-party complaints are unrelated.'),
    (122, 316, False, 'Blocked-hydrant parking and loud-party complaints are unrelated.'),
    (232, 252, False, 'Loud-party and illegal-dumping complaints are unrelated.'),
    (122, 550, False, 'Blocked-hydrant parking and loud-party complaints are unrelated.'),
    (252, 316, False, 'Illegal-dumping and loud-party complaints are unrelated.'),
    (1019, 1150, False, 'Sink plumbing and refrigerator complaints are unrelated.'),
    (943, 1018, False, 'Door and sink plumbing complaints are unrelated.'),
    (949, 1083, False, 'Water leak and pest complaints are unrelated.'),
    (949, 1149, False, 'Water leak and mold complaints are distinct reported conditions.'),
    (731, 955, False, 'Construction blockage and crash-cushion defect are separate conditions.'),
    (1281, 1400, False, 'Pothole and cave-in are separate roadway defects.'),
    (3820, 3991, False, 'Cave-in and pothole are separate roadway defects.'),
    (1255, 1291, False, 'Pothole and cave-in are separate roadway defects.'),
    (3883, 3968, False, 'Construction blockage and cave-in are separate conditions.'),
    (3036, 3057, False, 'Cave-in and pothole are separate roadway defects.'),
    (4672, 4764, True, 'Same tree location within one minute; the fallen branch is also hitting a building.'),
    (4390, 4398, True, 'Same tree location within two minutes; dead branches progressed to a cracked branch.'),
    (4641, 4842, True, 'Same tree location within two minutes; fallen branch is affecting cable lines.'),
    (4643, 4983, True, 'Same tree location within four minutes; one tree affects cables and blocks the street.'),
    (4684, 4720, True, 'Same tree location within seven minutes; a dead tree produced a fallen branch.')
]

def build_review_pairs():
    pairs = []
    for cluster_id, review in CLUSTER_REVIEWS.items():
        incident_groups = {}
        for group_number, incident_group in enumerate(review['event_groups']):
            for incident_id in incident_group:
                incident_groups[incident_id] = group_number
        reviewed_incidents = sorted(incident_groups)
        for incident_a, incident_b in combinations(reviewed_incidents, 2):
            same_event = incident_groups[incident_a] == incident_groups[incident_b]
            if same_event:
                rationale = 'Reviewed members belong to the same event group in cluster ' + str(cluster_id) + '.'
            else:
                rationale = 'Reviewed members belong to separate event groups despite sharing cluster ' + str(cluster_id) + '.'
            pairs.append((incident_a, incident_b, same_event, rationale, cluster_id))
    return pairs

async def build_pair_record(session, incident_a_id, incident_b_id, same_event, rationale, review_cluster_id=None):
    incident_a = aliased(Incident)
    incident_b = aliased(Incident)
    membership_a = aliased(IncidentClusterMember)
    membership_b = aliased(IncidentClusterMember)
    select_pair_statement = select(
        incident_a,
        incident_b,
        membership_a.cluster_id,
        membership_b.cluster_id,
        func.ST_Distance(incident_a.location, incident_b.location),
        1 - incident_a.embedding.cosine_distance(incident_b.embedding)
    ).join(
        membership_a,
        membership_a.incident_id == incident_a.id
    ).join(
        incident_b,
        incident_b.id == incident_b_id
    ).join(
        membership_b,
        membership_b.incident_id == incident_b.id
    ).where(
        incident_a.id == incident_a_id
    )
    result = await session.execute(select_pair_statement)
    first, second, first_cluster_id, second_cluster_id, distance, similarity = result.one()
    time_difference_seconds = abs(
        (first.source_created_at - second.source_created_at).total_seconds()
    )
    category_match = first.category == second.category
    return {
        'incident_a': first.source + ':' + first.external_id,
        'incident_b': second.source + ':' + second.external_id,
        'incident_a_id': first.id,
        'incident_b_id': second.id,
        'incident_a_cluster_id': first_cluster_id,
        'incident_b_cluster_id': second_cluster_id,
        'review_cluster_id': review_cluster_id,
        'category': first.category,
        'incident_b_category': second.category,
        'category_match': category_match,
        'incident_a_complaint_type': first.complaint_type,
        'incident_a_descriptor': first.descriptor,
        'incident_b_complaint_type': second.complaint_type,
        'incident_b_descriptor': second.descriptor,
        'distance_meters': round(float(distance), 2),
        'time_difference_seconds': round(time_difference_seconds, 2),
        'semantic_similarity': round(float(similarity), 4),
        'same_event': same_event,
        'review_confidence': 'high',
        'review_rationale': rationale
    }

async def build_gold_dataset():
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    pair_definitions = build_review_pairs()
    pair_definitions.extend([
        (incident_a, incident_b, same_event, rationale, None)
        for incident_a, incident_b, same_event, rationale in CROSS_CLUSTER_PAIRS
    ])
    seen_pairs = set()
    gold_records = []
    try:
        async with async_session() as session:
            for incident_a, incident_b, same_event, rationale, cluster_id in pair_definitions:
                pair_key = tuple(sorted((incident_a, incident_b)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                record = await build_pair_record(
                    session,
                    incident_a,
                    incident_b,
                    same_event,
                    rationale,
                    cluster_id
                )
                gold_records.append(record)
        gold_records.sort(
            key=lambda record: (
                record['incident_a_cluster_id'],
                record['incident_b_cluster_id'],
                record['incident_a_id'],
                record['incident_b_id']
            )
        )
        reviews = [
            {
                'cluster_id': cluster_id,
                'decision': review['decision'],
                'event_groups': review['event_groups'],
                'excluded_incidents': review['excluded_incidents'],
                'notes': review['notes']
            }
            for cluster_id, review in sorted(CLUSTER_REVIEWS.items())
        ]
        with open(REVIEWS_PATH, 'w') as f:
            json.dump(reviews, f, indent=2)
        with open(GOLD_PATH, 'w') as f:
            json.dump(gold_records, f, indent=2)
        positive_count = sum(record['same_event'] for record in gold_records)
        negative_count = len(gold_records) - positive_count
        cross_category_count = sum(not record['category_match'] for record in gold_records)
        print('Reviewed clusters:', len(reviews))
        print('Gold pairs:', len(gold_records))
        print('Positive pairs:', positive_count)
        print('Negative pairs:', negative_count)
        print('Cross-category pairs:', cross_category_count)
        print('Reviews:', REVIEWS_PATH)
        print('Gold dataset:', GOLD_PATH)
    finally:
        await close_database()

if __name__ == '__main__':
    asyncio.run(build_gold_dataset())
