#!/usr/bin/env python

"""
Compute distortion of each element.
"""

import argparse
import pymesh
import numpy as np
import numpy.linalg
import logging
import csv

def parse_args():
    parser = argparse.ArgumentParser(__doc__);
    parser.add_argument("--log", type=str, help="logging level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default="WARNING");
    parser.add_argument("--csv", type=str, help="output csv_file");
    parser.add_argument("input_mesh");
    parser.add_argument("output_mesh");
    return parser.parse_args();

def compute_distortion_energies(mesh):
    if mesh.num_voxels > 0 and mesh.vertex_per_voxel != 4:
        raise RuntimeError("Only tet mesh is supported for distortion computation");

    regular_tet = pymesh.generate_regular_tetrahedron();
    assembler = pymesh.Assembler(regular_tet);
    G = assembler.assemble("gradient");

    vertices = mesh.vertices;
    tets = mesh.voxels;
    Js = [ G * vertices[tet] for tet in tets ];

    J_F = np.array([np.trace(np.dot(J.T, J)) for J in Js]);
    J_det = np.array([numpy.linalg.det(J) for J in Js]);
    invert_J = lambda args: np.full((3,3), np.inf) if args[1] == 0 else numpy.linalg.inv(args[0])
    J_inv = map(invert_J, zip(Js, J_det));
    J_inv_F = np.array([np.trace(np.dot(Ji.T, Ji)) for Ji in J_inv]);

    conformal_amips = np.divide(J_F, np.cbrt(np.square(J_det)));
    finite_conformal_amips = np.isfinite(conformal_amips);
    symmetric_dirichlet = J_F + J_inv_F;
    finite_symmetric_dirichlet = np.isfinite(symmetric_dirichlet);
    orientations = pymesh.get_tet_orientations(mesh);
    orientations[orientations > 0] = 1;
    orientations[orientations < 0] = -1;

    num_degenerate_tets = np.count_nonzero(orientations==0);
    num_inverted_tets = np.count_nonzero(orientations<0);
    num_nonfinite_amips = np.count_nonzero(np.logical_not(finite_conformal_amips));
    num_nonfinite_dirichlet =\
            np.count_nonzero(np.logical_not(finite_symmetric_dirichlet));
    logger = logging.getLogger("Distorsion");
    if num_degenerate_tets > 0:
        logger.warn("degenerate tets: {}".format(num_degenerate_tets));
    if num_inverted_tets > 0:
        logger.warn("inverted tets: {}".format(num_inverted_tets));
    if num_nonfinite_amips > 0:
        logger.warn("Non-finite conformal AMIPS: {}".format(
            num_nonfinite_amips));
    if num_nonfinite_dirichlet > 0:
        logger.warn("Non-finite symmetric Dirichlet: {}".format(
            num_nonfinite_dirichlet));

    mesh.add_attribute("conformal_AMIPS");
    mesh.set_attribute("conformal_AMIPS", conformal_amips);
    mesh.add_attribute("finite_conformal_AMIPS");
    mesh.set_attribute("finite_conformal_AMIPS", finite_conformal_amips);
    mesh.add_attribute("symmetric_Dirichlet");
    mesh.set_attribute("symmetric_Dirichlet", symmetric_dirichlet);
    mesh.add_attribute("finite_symmetric_Dirichlet");
    mesh.set_attribute("finite_symmetric_Dirichlet", finite_symmetric_dirichlet);
    mesh.add_attribute("orientations");
    mesh.set_attribute("orientations", orientations);

def compute_tet_quality_measures(mesh):
    mesh.add_attribute("voxel_inradius");
    mesh.add_attribute("voxel_circumradius");
    inradius = mesh.get_attribute("voxel_inradius");
    circumradius = mesh.get_attribute("voxel_circumradius");
    radius_ratio = np.divide(inradius, circumradius);
    mesh.add_attribute("radius_ratio");
    mesh.set_attribute("radius_ratio", radius_ratio);
    mesh.add_attribute("voxel_dihedral_angle");
    dihedral_angle = mesh.get_voxel_attribute("voxel_dihedral_angle");
    if mesh.num_voxels == 0:
        min_dihedral_angle = np.zeros(0);
        max_dihedral_angle = np.zeros(0);
    else:
        min_dihedral_angle = np.amin(dihedral_angle, axis=1);
        max_dihedral_angle = np.amax(dihedral_angle, axis=1);
    mesh.add_attribute("voxel_min_dihedral_angle");
    mesh.set_attribute("voxel_min_dihedral_angle", min_dihedral_angle);
    mesh.add_attribute("voxel_max_dihedral_angle");
    mesh.set_attribute("voxel_max_dihedral_angle", max_dihedral_angle);
    mesh.add_attribute("voxel_radius_edge_ratio");
    mesh.add_attribute("voxel_edge_ratio");

def output_to_csv(mesh, csv_file):
    with open(csv_file, 'w') as fout:
        writer = csv.writer(fout);
        writer.writerow(["index", "edge_ratio", "radius_ratio",
            "min_dihedral_angle", "max_dihedral_angle", "radius_edge_ratio",
            "conformal_amips", "symmetric_dirichlet", "orientation"]);

        index = np.arange(mesh.num_voxels);
        edge_ratio = mesh.get_attribute("voxel_edge_ratio");
        radius_ratio = mesh.get_attribute("radius_ratio");
        min_dihedral = mesh.get_attribute("voxel_min_dihedral_angle");
        max_dihedral = mesh.get_attribute("voxel_max_dihedral_angle");
        re_ratio = mesh.get_attribute("voxel_radius_edge_ratio");
        amips = mesh.get_attribute("conformal_AMIPS");
        dirichlet = mesh.get_attribute("symmetric_Dirichlet");
        orientation = mesh.get_attribute("orientations");

        for i in range(mesh.num_voxels):
            writer.writerow([i,
                edge_ratio[i],
                radius_ratio[i],
                min_dihedral[i],
                max_dihedral[i],
                re_ratio[i],
                amips[i],
                dirichlet[i],
                orientation[i] ]);

def main():
    args = parse_args();
    mesh = pymesh.load_mesh(args.input_mesh);
    if mesh.num_voxels > 0 and mesh.vertex_per_voxel != 4:
        raise RuntimeError("Only tet mesh is supported for distortion computation");

    numeric_level = getattr(logging, args.log, None);
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel);
    logging.basicConfig(level=numeric_level);

    compute_distortion_energies(mesh);
    compute_tet_quality_measures(mesh);
    if args.csv != None:
        output_to_csv(mesh, args.csv);

    pymesh.save_mesh(args.output_mesh, mesh, *mesh.attribute_names);

if __name__ == "__main__":
    main();