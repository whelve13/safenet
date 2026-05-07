def compute_lps_array(pattern: str) -> list[int]:
    length = 0
    lps = [0] * len(pattern)
    i = 1

    while i < len(pattern):
        if pattern[i] == pattern[length]:
            length += 1
            lps[i] = length
            i += 1
        else:
            if length != 0:
                length = lps[length - 1]
            else:
                lps[i] = 0
                i += 1
    return lps

def kmp_search(text: str, pattern: str) -> list[int]:
    if not pattern or not text:
        return []

    text = text.lower()
    pattern = pattern.lower()
    
    M = len(pattern)
    N = len(text)
    lps = compute_lps_array(pattern)
    
    indices = []
    i = 0  # index for text
    j = 0  # index for pattern
    
    while (N - i) >= (M - j):
        if pattern[j] == text[i]:
            j += 1
            i += 1
            
        if j == M:
            indices.append(i - j)
            j = lps[j - 1]
        elif i < N and pattern[j] != text[i]:
            if j != 0:
                j = lps[j - 1]
            else:
                i += 1
                
    return indices