import json

from fab.tools import run_command

data_json = run_command(['gh', 'pr', 'status', '--json', 'number,author,reviews'], capture_output=True)
data = json.loads(data_json)

for pr in data['createdBy']:

    print('-------------')
    print('number', pr['number'])
    print(f"author {pr['author']['name']} ({pr['author']['login']})")

    reviewers_str = ', '.join({review['author']['login'] for review in pr['reviews']})
    print('reviewed by', reviewers_str)

    print('')

# todo: there will probably be some data in here to print, not seen that yet.
# print(f"{len(data['needsReview'])} need review")
