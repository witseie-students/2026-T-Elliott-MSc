# backend/knowledge_graph_generator/management/commands/extract_abstracts.py
# Description: This script fetches abstracts related to a specified query from PubMed and saves them to the database.

from Bio import Entrez
from datetime import datetime
from knowledge_graph_generator.models import Abstract
import time

# Set your email for Entrez API
Entrez.email = '2129200@students.wits.ac.za'

def fetch_and_save_pubmed_abstracts(query, count=10, retries=3, timeout=5):
    """
    Fetch abstracts from PubMed based on a query and save them to the database.
    
    Parameters:
        query (str): The search query for PubMed (e.g., "pancreatic cancer").
        count (int): The number of abstracts to fetch and save (default is 10).
        retries (int): The number of retry attempts if fetching an abstract fails (default is 3).
        timeout (int): The wait time (in seconds) before retrying a failed fetch (default is 5).
    """
    def search_papers(query, retmax=10):
        """
        Search PubMed for the query and return the list of PubMed IDs.
        """
        handle = Entrez.esearch(db='pubmed',
                                sort='relevance',
                                retmax=str(retmax),  # Retrieve up to 'retmax' papers
                                retmode='xml',
                                term=query)
        results = Entrez.read(handle)
        id_list = results.get('IdList', [])
        if not id_list:
            print(f"No abstracts found for query: {query}")
        return id_list

    def fetch_abstract_with_retry(pmid, retries=3, timeout=5):
        """
        Fetch a single abstract with retries in case of failure.
        """
        for attempt in range(1, retries + 1):
            try:
                handle = Entrez.efetch(db='pubmed', retmode='xml', id=pmid)
                paper = Entrez.read(handle)
                print(f"Successfully fetched abstract for PMID: {pmid} on attempt {attempt}.")
                return paper
            except Exception as e:
                print(f"Error fetching PMID: {pmid} (Attempt {attempt}/{retries}): {e}")
                if attempt < retries:
                    print(f"Retrying after {timeout} seconds...")
                    time.sleep(timeout)
                else:
                    print(f"Failed to fetch abstract for PMID: {pmid} after {retries} attempts. Skipping.")
                    return None

    def fetch_abstracts(id_list):
        """
        Fetch and return abstracts and details for each PubMed ID in id_list.
        """
        abstracts = []
        for idx, pmid in enumerate(id_list, start=1):
            print(f"Fetching details for paper {idx}/{len(id_list)} (PMID: {pmid})...")
            paper = fetch_abstract_with_retry(pmid, retries, timeout)
            if not paper:
                continue  # Skip to the next PMID if fetching failed
            
            try:
                article = paper['PubmedArticle'][0]['MedlineCitation']['Article']
            except (KeyError, IndexError):
                print(f"Skipping paper ID {pmid}: Unable to fetch article details.")
                continue
            
            # Extract title
            title = article.get('ArticleTitle', 'No Title Available')
            
            # Extract abstract text if available
            try:
                abstract_text = " ".join(article['Abstract']['AbstractText'])
            except KeyError:
                abstract_text = 'No Abstract Available'
            
            # Extract journal name
            journal = article['Journal'].get('Title', 'No Journal Name Available')
            
            # Extract publication date
            pub_date = article['Journal']['JournalIssue'].get('PubDate', {})
            
            # Compile the extracted data
            abstracts.append({
                "pmid": pmid,
                "title": title,
                "abstract_text": abstract_text,
                "journal": journal,
                "publication_date": pub_date,
            })
        return abstracts

    # Search for abstracts
    print(f"Searching for up to {count} abstracts for query: '{query}'...")
    id_list = search_papers(query, retmax=count)
    if not id_list:
        print(f"No abstracts found for query: {query}")
        return

    # Fetch abstract details
    print(f"Fetching abstracts for {len(id_list)} papers...")
    abstract_details = fetch_abstracts(id_list)

    # Save abstracts to the database
    print("Saving abstracts to the database...")
    for idx, paper in enumerate(abstract_details, start=1):
        pubmed_id = paper["pmid"]
        title = paper["title"]
        abstract_text = paper["abstract_text"]
        journal = paper["journal"]
        pub_date = paper["publication_date"]
        
        # Convert publication date to a datetime object, or use None if incomplete
        publication_date = None
        try:
            year = int(pub_date.get('Year', '1900'))
            month = int(pub_date.get('Month', '1'))
            day = int(pub_date.get('Day', '1'))
            publication_date = datetime(year, month, day)
        except (ValueError, KeyError):
            publication_date = None

        # Save to database, avoiding duplicates
        _, created = Abstract.objects.get_or_create(
            pubmed_id=pubmed_id,
            defaults={
                'title': title,
                'abstract_text': abstract_text,
                'journal': journal,
                'publication_date': publication_date,
            }
        )
        if created:
            print(f"({idx}/{len(abstract_details)}) Saved new abstract for PubMed ID: {pubmed_id}")
        else:
            print(f"({idx}/{len(abstract_details)}) Abstract for PubMed ID: {pubmed_id} already exists in the database.")

    print("Completed fetching and saving all abstracts.")




