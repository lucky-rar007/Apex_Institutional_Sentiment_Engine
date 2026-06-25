def levenshtein_distance(s1, s2):
    """
    Computes the Levenshtein distance between two strings.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]

def string_similarity(s1, s2):
    """
    Computes the similarity ratio between two strings based on Levenshtein distance.
    Ranges from 0.0 (completely different) to 1.0 (identical).
    """
    s1 = s1.lower().strip().replace('_', ' ').replace('-', ' ')
    s2 = s2.lower().strip().replace('_', ' ').replace('-', ' ')
    
    distance = levenshtein_distance(s1, s2)
    max_len = max(len(s1), len(s2))
    
    if max_len == 0:
        return 1.0
        
    return 1.0 - (distance / max_len)

def match_and_register_event(registry, proposed_type, description, category):
    """
    Compares the proposed event type with all event types in the in-memory registry.
    If a close match (similarity >= 0.85) exists, maps to that match.
    Otherwise, registers the new event type in the registry.
    Returns the resolved event type.
    """
    proposed_type = proposed_type.strip().lower()
    
    # Check if exact match exists first
    if proposed_type in registry:
        return proposed_type
        
    best_match = None
    max_similarity = 0.0
    
    for existing_type in registry.keys():
        sim = string_similarity(proposed_type, existing_type)
        if sim > max_similarity:
            max_similarity = sim
            best_match = existing_type
            
    # Check threshold (Rule 6: 0.85)
    if max_similarity >= 0.85:
        print(f"    [Registry] Mapped proposed event '{proposed_type}' to existing '{best_match}' (Similarity: {max_similarity:.2f})")
        return best_match
    else:
        print(f"    [Registry] No close match found. Registering new event type in-memory: '{proposed_type}' (Category: '{category}')")
        registry[proposed_type] = {
            "description": description.strip(),
            "category": category.strip()
        }
        try:
            from storage.db_client import add_event_type
            add_event_type(proposed_type, category, description)
        except Exception as e:
            print(f"    [Registry Error] Failed to save new event type to DB: {e}")
        return proposed_type

