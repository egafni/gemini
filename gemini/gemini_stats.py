#!/usr/bin/env python
import sqlite3
import os
import sys
import numpy as np
import cPickle
import zlib
import collections

import gemini_utils as util
from gemini_constants import *


def get_tstv(c, args):
    """
    Report the transition / transversion ratio.
    """
    ts_cmd = "SELECT count(1) \
           FROM  variants \
           WHERE type = \'snp\' \
           AND   sub_type = \'ts\'"
    tv_cmd = "SELECT count(1) \
          FROM  variants v \
          WHERE type = \'snp\' \
          AND   sub_type = \'tv\'"
    # get the number of transitions
    c.execute(ts_cmd)
    ts = c.fetchone()[0]
    # get the number of transversions
    c.execute(tv_cmd)
    tv = c.fetchone()[0]
    # report the transitions, transversions, and the ts/tv ratio
    print "ts" + '\t' + \
          "tv" + '\t' + "ts/tv"
    print str(ts) + '\t' + \
        str(tv) + '\t' + \
        str(round(float(ts) / float(tv),4))


def get_tstv_coding(c, args):
    """
    Report the transition / transversion ratio in coding regions.
    """
    ts_cmd = "SELECT count(1) \
           FROM variants v \
           WHERE v.type = \'snp\' \
           AND v.sub_type = \'ts\' \
           AND v.is_coding = 1"
    tv_cmd = "SELECT count(1) \
          FROM variants v \
          WHERE v.type = \'snp\' \
          AND v.sub_type = \'tv\' \
          AND v.is_coding = 1"
    # get the number of transitions
    c.execute(ts_cmd)
    ts = c.fetchone()[0]
    # get the number of transversions
    c.execute(tv_cmd)
    tv = c.fetchone()[0]
    # report the transitions, transversions, and the ts/tv ratio
    print "ts" + '\t' + \
          "tv" + '\t' + "ts/tv"
    print str(ts) + '\t' + \
        str(tv) + '\t' + \
        str(round(float(ts) / float(tv),4))


def get_tstv_noncoding(c, args):
    """
    Report the transition / transversion ratio in coding regions.
    """
    ts_cmd = "SELECT count(1) \
           FROM variants v \
           WHERE v.type = \'snp\' \
           AND v.sub_type = \'ts\' \
           AND v.is_coding = 0"
    tv_cmd = "SELECT count(1) \
          FROM variants v \
          WHERE v.type = \'snp\' \
          AND v.sub_type = \'tv\' \
          AND v.is_coding = 0"
    # get the number of transitions
    c.execute(ts_cmd)
    ts = c.fetchone()[0]
    # get the number of transversions
    c.execute(tv_cmd)

    tv = c.fetchone()[0]
    # report the transitions, transversions, and the ts/tv ratio
    print "ts" + '\t' + \
          "tv" + '\t' + "ts/tv"
    print str(ts) + '\t' + \
        str(tv) + '\t' + \
        str(round(float(ts) / float(tv),4))


def get_snpcounts(c, args):
    """
    Report the count of each type of SNP.
    """
    query = "SELECT ref, alt, count(1) \
             FROM   variants \
             WHERE  type = \'snp\' \
             GROUP BY ref, alt"

    # get the ref and alt alleles for all snps.
    c.execute(query)
    print '\t'.join(['type', 'count'])
    for row in c:
        print '\t'.join([str(row['ref']) + "->" + str(row['alt']),
                         str(row['count(1)'])])


def get_sfs(c, args):
    """
    Report the site frequency spectrum
    """
    precision = 3
    query = "SELECT round(aaf," + str(precision) + "), count(1) \
             FROM variants \
             GROUP BY round(aaf," + str(precision) + ")"

    c.execute(query)
    print '\t'.join(['aaf', 'count'])
    for row in c:
        print '\t'.join([str(row[0]), str(row[1])])


def get_mds(c, args):
    """
    Compute the pairwise genetic distance between each sample.
    """
    idx_to_sample = {}
    c.execute("select sample_id, name from samples")
    for row in c:
        idx_to_sample[int(row['sample_id']) - 1] = row['name']

    query = "SELECT DISTINCT v.variant_id, v.gt_types\
    FROM variants v\
    WHERE v.type = 'snp'"
    c.execute(query)

    # keep a list of numeric genotype values
    # for each sample
    genotypes = collections.defaultdict(list)
    for row in c:

        gt_types = np.array(cPickle.loads(zlib.decompress(row['gt_types'])))

        # at this point, gt_types is a numpy array
        # idx:  0 1 2 3 4 5 6 .. #samples
        # type [0 1 2 1 2 0 0 ..         ]
        for idx, gt_type in enumerate(gt_types):
            sample = idx_to_sample[idx]
            genotypes[sample].append(gt_type)

    mds = collections.defaultdict(float)
    # convert the genotype list for each sample
    # to a numpy array for performance.
    # masks stores an array of T/F indicating which genotypes are
    # known (True, [0,1,2]) and unknown (False [-1]).
    masks = {}
    for s in genotypes:
        sample = str(s)
        x = np.array(genotypes[sample])
        genotypes[sample] = x
        masks[sample] = \
            np.ma.masked_where(genotypes[sample] != UNKNOWN,
                               genotypes[sample]).mask

    # compute the euclidean distance for each s1/s2 combination
    # using numpy's vectorized sum() and square() operations.
    # we use the mask arrays to identify the indices of known genotypes
    # for each sample.  by doing a bitwise AND of the mask arrays for the
    # two samples, we have a mask array of variants where __both__ samples
    # were called.
    for sample1 in genotypes:
        for sample2 in genotypes:
            pair = (sample1, sample2)
            # which variants have known genotypes for both samples?
            both_mask = masks[str(sample1)] & masks[str(sample2)]
            genotype1 = genotypes[sample1]
            genotype2 = genotypes[sample2]

            # distance between s1 and s2:
            eucl_dist = float(np.sum(np.square((genotype1 - genotype2)[both_mask]))) \
                / \
                float(np.sum(both_mask))

            mds[pair] = eucl_dist

    # report the pairwise MDS for each sample pair.
    print "sample1\tsample2\tdistance"
    for pair in mds:
        print "\t".join([str(pair[0]), str(pair[1]), str(round(mds[pair],4))])


def get_variants_by_sample(c, args):
    """
    Report the number of variants observed for each sample
    where the sample had a non-ref genotype
    """
    idx_to_sample = util.map_indicies_to_samples(c)

    # report.
    print '\t'.join(['sample', 'total'])

    query = "SELECT sample_id, \
             (num_het + num_hom_alt) as total \
             FROM sample_genotype_counts"
    c.execute(query)
    for row in c:
        sample = idx_to_sample[row['sample_id']]
        print "\t".join(str(s) for s in [sample,
                                         row['total']])


def get_gtcounts_by_sample(c, args):
    """
    Report the count of each genotype class
    observed for each sample.
    """
    idx_to_sample = util.map_indicies_to_samples(c)

    # report.
    print '\t'.join(['sample', 'num_hom_ref', 'num_het',
                     'num_hom_alt', 'num_unknown', 'total'])

    query = "SELECT *, \
             (num_hom_ref + num_het + num_hom_alt + num_unknown) as total \
             FROM sample_genotype_counts"
    c.execute(query)
    # count the number of each genotype type obs. for each sample.
    for row in c:
        sample = idx_to_sample[row['sample_id']]
        print "\t".join(str(s) for s in [sample,
                                         row['num_hom_ref'],
                                         row['num_het'],
                                         row['num_hom_alt'],
                                         row['num_unknown'],
                                         row['total']])


def stats(parser, args):

    if os.path.exists(args.db):
        conn = sqlite3.connect(args.db)
        conn.isolation_level = None
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        if args.tstv:
            get_tstv(c, args)
        elif args.tstv_coding:
            get_tstv_coding(c, args)
        elif args.tstv_noncoding:
            get_tstv_noncoding(c, args)
        elif args.snp_counts:
            get_snpcounts(c, args)
        elif args.sfs:
            get_sfs(c, args)
        elif args.variants_by_sample:
            get_variants_by_sample(c, args)
        elif args.genotypes_by_sample:
            get_gtcounts_by_sample(c, args)
        elif args.mds:
            get_mds(c, args)
