#!/usr/bin/env python
#-*- coding: utf-8 -*-

# Tools for working with poems
#
# Licensed under GPLv2 or later.

from __future__ import print_function
import json, os, re, sys
from collections import defaultdict
from string import ascii_lowercase
from Levenshtein import distance
from .countsyl import count_syllables

try:
    from nltk.corpus import cmudict
    cmu = cmudict.dict()
except:
    with open(os.path.join(os.path.dirname(__file__), 'cmudict/cmudict.json')) as json_file:
        cmu = json.load(json_file)

def elided_d(word):
    if word[-2:] == "'d":
        return word[:-2] + "ed"
    return word

def tokenize(poem):
    tokens = []
    for line in poem.split('\n'):
        line       = line.replace('-', ' ') # need to find a better tokenizer, but this works for now
        no_hyphens = line.replace('—', ' ') 
        cleaned    = re.sub(r'[^0-9a-zA-Z\s\']', '', no_hyphens) # keep apostrophes
        tokens.append([elided_d(word) for word in cleaned.strip().split(' ')])
    return tokens

def levenshtein(tocompare, candidates, linebyline=False):
    z = defaultdict(int)
    if linebyline == True:
        for line in tocompare:
            for v in candidates.items():
                z[v[0]] += distance(line, v[1])
    else:
        num_lines = len(tocompare)
        for v in candidates.items():
            expanded = (v[1] * (num_lines // len(v[1]) + 1))[:num_lines]
            z[v[0]] += distance(tocompare, expanded)
    best_guess = min(z, key = z.get)
    return best_guess

def stress(word):
    if word.lower() not in cmu:
        return '1' + '0' * (count_syllables(word) - 1) # provisional logic for adding stress is to stress first syllable only
    else:
        pronunciation_string = str(''.join([a for a in min(cmu[word.lower()])]))
        stress_numbers       = ''.join([x.replace('2', '1') for x in list(pronunciation_string) if x.isdigit()]) # not interested in secondary stress
        return stress_numbers   

def scanscion(poem):
    poem = tokenize(poem)

    line_stresses = []
    currline      = 0

    for line in poem:
        line_stresses.append([])
        [line_stresses[currline].append(stress(word)) for word in line if word]
        currline += 1

    return line_stresses

def rhymes(w1, w2, level=2, throwError=False):
     try:
         syllables = [' '.join([str(c) for c in lst]) for lst in cmu[w1.lower()]]
     except KeyError:
         if throwError == True:
             raise KeyError(w1 + ' not found in CMU dictionary')
         return False
     try:
         syllables2 = [' '.join([str(c) for c in lst]) for lst in cmu[w2.lower()]]
     except KeyError:
         if throwError == True:
             raise KeyError(w2 + ' not found in CMU dictionary')
         return False
     for syllable in syllables:
         for syllable2 in syllables2:
             if syllable2[-level:] == syllable[-level:]:
                 return True
             else:
                 return False

def rhyme_scheme(poem):
    poem = tokenize(poem)

    last_words = [s[-1] for s in poem if s]
    scheme     = ['X'] * len(last_words)

    rhyme_notation = list(ascii_lowercase)

    currline = currrhyme = 0
    for word in last_words:
        rhymed = False
        for i in range(currline + 1, len(last_words)):
            if scheme[i] == 'X' : # if word is not already part of a rhyme scheme
                if not word:
                    scheme[currline] = ' '
                elif rhymes(word, last_words[i], 2, False):                    
                    scheme[currline] = scheme[i] = rhyme_notation[currrhyme]
                    rhymed           = True
        if rhymed == True:
            currrhyme += 1
        currline += 1
   
    # find duplicate lines, important for some forms like rondeau
    D = defaultdict(list)
    for lineno, line in enumerate(poem):
        D[tuple(line)].append(lineno)
    duplicates = {
                   k : v for k,
                   v in D.items() if len(k) > 1 and len(v) > 1}  
    for num in sorted(duplicates.values()):
        for n in num:
            scheme[n] = scheme[n].upper()

    return scheme

def guess_metre(poem):
    joined       = [''.join(line) for line in scanscion(poem) if line]
    line_lengths = [len(line) for line in joined]
    num_lines    = len(joined)

    possible_metres = {
                        'iambic trimeter'     : '010101',
                        'iambic tetrameter'   : '01010101',
                        'iambic pentameter'   : '0101010101',
                        'trochaic tetrameter' : '10101010',
                        'trochaic pentameter' : '1010101010'}

    guessed_metre = levenshtein(joined, possible_metres, linebyline=True)
    return joined, num_lines, line_lengths, guessed_metre

def guess_rhyme_type(poem):
    joined    = ''.join([l for l in rhyme_scheme(poem)])

    possible_rhymes = {
                             'couplets'             : 'aabb ccdd eeff',
                             'alternate rhyme'      : 'abab cdcd efef ghgh',
                             'enclosed rhyme'       : 'abba cddc effe',
                             'rima'                 : 'ababcbcdcdedefefgfghg',
                             'rondeau rhyme'        : 'aabba aab C aabba C',
                             'shakespearean sonnet' : 'ababcdcdefefgg',
                             'limerick'             : 'aabba',
                             'no rhyme'             : 'XXXXX'}

    guessed_rhyme = levenshtein(joined, possible_rhymes, linebyline=False)
    return joined, guessed_rhyme

def stanza_lengths(rhymescheme):
    stanzas, j, inspace = [0], 0, False
    for i in rhymescheme:
        if i == ' ':
            if not inspace:
                j += 1;
                stanzas += [0];
                inspace = True
        else:
            stanzas[j] = stanzas[j] + 1;
            inspace = False
    joined = ','.join(map(str,stanzas)) + ","

    possible_stanzas = {
                             'sonnet'             : '14,',
                             'tercets'             : '3,'}

    guessed_stanza = levenshtein(joined, possible_stanzas, linebyline=False)
    return joined, guessed_stanza

def guess_form(poem, verbose=False):
    def within_ranges(line_properties, ranges):
        if all([ranges[i][0] <= line_properties[i] <= ranges[i][1] for i in range(len(ranges))]):
            return True

    metrical_scheme, num_lines, line_lengths, metre = guess_metre(poem)
    rhyme_scheme_string, rhyme = guess_rhyme_type(poem)
    stanza_length_string, stanza = stanza_lengths(rhyme_scheme_string)

    if verbose == True:
        print("Metre: " + ' '.join(metrical_scheme))
        print("Rhyme scheme: " + rhyme_scheme_string)
        print("Stanza lengths: " + stanza_length_string)
        print()
        print("Closest metre: " + metre)
        print("Closest rhyme: " + rhyme)
        print("Closest stanza type: " + stanza)
        print("Guessed form: ",end="")

    if num_lines == 3 and within_ranges(line_lengths, [(4, 6), (6, 8), (4, 6)]):
        return 'haiku'

    if num_lines == 5:
        if line_lengths == [1, 2, 3, 4, 10]:
            return 'tetractys'

        if within_ranges(line_lengths, [(8, 11), (8, 11), (5, 7), (5, 7), (8, 11)]):
            return 'limerick'

        if within_ranges(line_lengths, [(4, 6), (6, 8), (4, 6), (6, 8), (6, 8)]):
            return 'tanka'

        if rhyme == 'no rhyme':
            return 'cinquain'

    if num_lines == 8:
        if within_ranges(line_lengths, [(10, 12) * 11]) and rhyme == 'rima':
            return 'ottava rima'

    if num_lines == 14:
        if metre == 'iambic pentameter' and rhyme == 'shakespearean sonnet' or rhyme == 'alternate rhyme':
            return 'Shakespearean sonnet'
        return 'sonnet with ' + metre + ' or irregular meter'

    if num_lines == 15:

        return 'rondeau'

    if rhyme == 'alternate rhyme' and metre == 'iambic tetrameter':
        return 'ballad stanza'

    if rhyme == 'couplets' and metre == 'iambic pentameter':
        return 'heroic couplets'

    if metre == 'iambic pentameter':
        return 'blank verse'

    return 'unknown form' 

if __name__ == '__main__':
    with open(sys.argv[1]) as f:
        print(guess_form(f.read(), verbose=True))
