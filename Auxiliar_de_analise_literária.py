import requests
import json
import os
import time
import networkx as nx
import pdb
import matplotlib.pyplot as plt
import pickle
import textwrap

S2_API_KEY = input("Paste the API KEY: ")

def get_boolean_input():
    while True:
        user_input = input("Please enter 'yes' or 'no': ").lower()
        if user_input == 'yes':
            return True
        elif user_input == 'no':
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

print("Use a saved grah? ")
if not get_boolean_input():

    print("Creating the graph")
    authorsNames = []
    articlesNames = []

    authors = []
    qualityWorks = []
    references = []
    # Used to prevent getting authors from another field with the same name
    Field = input("Type the field, Ex: Computer Science: ")

    print("Enter custom author list?")
    if get_boolean_input():
        name = input("File with the authors list: ")
        with open(f'{name}') as f:
            authorsNames = f.read().splitlines()

    print("Enter custom article list?")
    if get_boolean_input():

        name = input("File with the articles list: ")
        with open(f'{name}') as f:
            articlesNames = f.read().splitlines()

    """Getting authors Id's.

    WARNING: There's no guarantee that the fetched authors will be the desired ones (the code prioritize the most famous ones in the field that match the name), if some data looks strange, checking on the Semantic Scholar website is recommended.
    """

    for author in authorsNames:
      first,midle,*last = author.split(' ')
      last = last if last else " "

      # Don't stop until get the authors, ignoring failures
      while True:
        try:
          time.sleep(.3)
          rsp = requests.get(f"https://api.semanticscholar.org/graph/v1/author/search?query={first}+{midle}+{last}",
                         headers={'X-API-KEY': S2_API_KEY},
                         params={'fields': 'authorId,name,citationCount,papers,papers.fieldsOfStudy','limit': '50'})

          rsp.raise_for_status()
          break

        except requests.exceptions.RequestException:
          pass


      # add the first author on the search results
      data = rsp.json()['data']
      data = sorted(data, key=lambda x:x['citationCount'])
      data.reverse()

      # get correct author by field of study
      i = 0

      if not data:
        break

      while True:

        if data and data[i] and data[i]['papers']:
          # Try to find a paper that satisfies the conditions
          iteration_count, found_paper = next(
              (
              (index, paper)
              for index, paper in enumerate(data[i]['papers'])
              if (paper['fieldsOfStudy'] is not None) and (Field in paper['fieldsOfStudy'])
              ),
              (None, None)
          )

          # Check if a valid paper was found or if the maximum iterations are reached
          if found_paper is not None and iteration_count < 10:
            #print(f"Iteration {iteration_count}: {found_paper=}")
            print(f"{data[i]['name']}\t citations: {data[i]['citationCount']}  papers: {len(data[i]['papers'])}")

            del data[i]['papers']
            authors.append(data[i])
            break

        # Move to the next index
        if i < len(data)-1:
          i += 1
        # If failed to find go to the next on the list
        else:
          break

    """Getting the articles"""

    for article in articlesNames:
      try:
        time.sleep(0.3)
        rsp = requests.get(f"https://api.semanticscholar.org/graph/v1/paper/autocomplete?query={article}",
                        headers={'X-API-KEY': S2_API_KEY},
                        params={'limit': '5'})

        rsp.raise_for_status()
        if rsp.json()["matches"]:

          item = rsp.json()['matches'][0]

          rsp = requests.get(f"https://api.semanticscholar.org/graph/v1/paper/{item['id']}",
                        headers={'X-API-KEY': S2_API_KEY},
                        params={'fields': 'title,paperId,fieldsOfStudy,references,references.title,references.citationCount,references.influentialCitationCount,citationCount,influentialCitationCount'})
          rsp.raise_for_status()

          paper = rsp.json()

          if paper['paperId'] is not None:
            # add all papers cited by the paper
            ref = []
            for x in paper['references']:
              if x['paperId'] is not None:
                x['quality'] = False
                ref.append(x)

            references.append(ref)

            # add paper
            del paper['references']
            paper['quality'] = True
            qualityWorks.append(paper)

        else:
          print(f"Could not find {article}")

      except requests.exceptions.RequestException:
        pass

    """Getting author's publications and references"""

    for author in authors:
      # Get a list of all authors publications and their respectives references

      while True:
        try:
          time.sleep(0.3)
          rsp = requests.get(f"https://api.semanticscholar.org/graph/v1/author/{author['authorId']}/papers",
                         headers={'X-API-KEY': S2_API_KEY},
                         params={'fields': 'title,paperId,fieldsOfStudy,references,references.title,references.citationCount,references.influentialCitationCount,citationCount,influentialCitationCount',
                                 'limit': 900})
                         # reference.citationCount, etc

          rsp.raise_for_status()
          break

        except requests.exceptions.RequestException:
          pass

      data = rsp.json()['data']

      for paper in data:
        if paper['paperId'] is not None:
          # add all papers cited by the paper
          ref = []
          for x in paper['references']:
            if x['paperId'] is not None:
              x['quality'] = False
              ref.append(x)

          #print(ref)
          references.append(ref)

          # add paper
          del paper['references']
          paper['quality'] = True
          qualityWorks.append(paper)

    for paper in qualityWorks:
      if paper['fieldsOfStudy']:
        if Field not in paper['fieldsOfStudy']:
          #print(f"Deleted not in the field {paper['title']}")
          del paper

    """We now have a list filled with papers and another list filed with a list of that paper references. Thus, basically a adjacency list.

    As for now, this list only contains the most important work (the writings of handpicked authors) that we will consider to be of high quality.

    Adding depth means to add the references's references into our graph.
    """

    nodes = qualityWorks.copy()
    edges = references.copy()
    qualityIds = [x['paperId'] for x in qualityWorks]

    # add one more depth into the search
    def addDepth():
      lenght = len(edges)

      for i in range(lenght):
        print(f"{i} / {lenght}")
        # if has reference
        if edges[i]:
          for paper in edges[i]:
            end = False

            # add reference paper into the node list
            if paper not in nodes:
              nodes.append(paper)
            # if is already prossed, go to the next
            else:
              continue

            # get paper references
            while True:
              try:

                time.sleep(0.1)
                rsp = requests.get(f"https://api.semanticscholar.org/graph/v1/paper/{paper['paperId']}/references",
                              headers={'X-API-KEY': S2_API_KEY},
                              params={'fields': 'title,fieldsOfStudy,citationCount,influentialCitationCount'})
                rsp.raise_for_status()
                break

              except requests.exceptions.HTTPError as err:
                if rsp.status_code == 404:
                  end = True

              except requests.exceptions.RequestException as e:
                print(e)
                pass

            if end:
              break

            data = rsp.json()['data']
            #print(paper['title'],len(data))

            # add the paper's references as his edges
            ref = []
            for x in data:
              if x['citedPaper']['paperId'] is not None and x['citedPaper']['fieldsOfStudy']:
                if Field in x['citedPaper']['fieldsOfStudy']:
                  if x['citedPaper']['paperId'] in qualityIds:
                    x['citedPaper']['quality'] = True
                  else:
                    x['citedPaper']['quality'] = False

                  ref.append(x['citedPaper'])

            edges.append(ref)

    for i in range(2):
      addDepth()

    print(len(nodes))
    print(len(edges))

    """Create or upload(next cell) a graph"""

    G = nx.DiGraph()

    atributes = ['citationCount','influentialCitationCount','quality','title']

    for i,l in enumerate(edges):
      for edge in l:

        if edge['paperId'] in qualityIds:
          edge['quality'] = True

        # Calculate the edge weight
        if nodes[i]['quality'] == True:
          influence = 0
        else:
          # Reversing the weights so that it has a inverse effect
          if nodes[i]['influentialCitationCount'] and nodes[i]['citationCount']:
            influence = 1/(nodes[i]['citationCount'] + 5*nodes[i]['influentialCitationCount'])
          else:
            if nodes[i]['citationCount']:
              influence = 1/(nodes[i]['citationCount'])
            else:
              influence = 0.5

        ne = {'influence': influence}

        # Add references as edges and nodes, as needed
        if edge not in nodes:
          nn = {key: edge[key] for key in atributes}

          if edge['paperId'] in qualityIds:
            nn['quality'] = True

          G.add_nodes_from([(edge['paperId'],nn)])
          G.add_edges_from([(edge['paperId'],nodes[i]['paperId'],ne)])

        else:
          G.add_edges_from([(edge['paperId'],nodes[i]['paperId'],ne)])

    # Add the rest of nodes
    for node in nodes:
      ne = {key: node[key] for key in atributes}
      G.add_nodes_from([(node['paperId'],ne)])

    print("Saving graph to literature.gpiclke")
    with open('literature.gpickle', 'wb') as f:
      pickle.dump(G, f, pickle.HIGHEST_PROTOCOL)

else:

    """Upload a graph"""

    name = input("Graph file name: ")
    with open(name, 'rb') as f:
        G = pickle.load(f)

"""Paper ranking"""

ranking = []

for node,data in G.nodes(data=True):
  # skip calculation on quality papers
  if data['quality']:
    continue

  sum = 0
  counter = 0
  for work in qualityWorks:

    # calculate distance using dijkstra
    try:
      sum = sum + nx.shortest_path_length(G, source=node, target=work['paperId'], weight='influence')
    # base number is lower when there's no path
    except nx.NetworkXNoPath:
      counter = counter + 1

  if sum == 0:
    avg = 0
  else:
    avg = (len(qualityWorks) - counter)/sum

  if data['influentialCitationCount'] and data['citationCount']:
    score = data['citationCount'] + 5*data['influentialCitationCount']
  else:
    if data['citationCount']:
      score = data['citationCount']
    else:
      score = 1

  # avg will be a small value as the weights are reversed
  score = score * avg
  ranking.append({'score':score,'title':data['title'],'id':node})

ranking = sorted(ranking, key=lambda x:x['score'])
ranking.reverse()

top = ranking[:20]

topIds = [x['id'] for x in top]

subgraph = G.subgraph(qualityIds + topIds)

# quality -> red
# influent (top 10) -> orange
# the rest -> blue
node_colors = ['orange' if node in topIds else 'red' if node in qualityIds else 'blue' for node,data in subgraph.nodes(data=True)]

for paper in top:
  print(paper['title'])

# Draw the graph
pos = nx.spring_layout(subgraph, k=1.7)
nx.draw(subgraph, pos, node_color=node_colors, font_color="black", font_weight="bold", edge_color="gray", linewidths=1)

#node_labels = {node: '\n'.join(textwrap.wrap(data['title'], width=26)) for node,data in subgraph.nodes(data=True)}
#nx.draw_networkx_labels(G, pos, labels=node_labels,font_size=6, verticalalignment="bottom")

plt.show()
