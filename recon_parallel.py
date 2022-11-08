from ast import arg, parse
from multiprocessing.sharedctypes import Value
from turtle import back
import h5py
import argparse
import os
import numpy as np
import math
import cold
import shutil

DATASETS = ['lau', 'pos', 'sig', 'ind']
PROC_OUT_DIR = 'proc_results'
RECON_OUT_DIR = 'recon'
ALL_OUTS = 'all_recons'

def parse_args():
    parser = argparse.ArgumentParser(
        description='Script to reconstruct output from the proc dumps in a run.'
    )
    parser.add_argument(
        'config_fp',
        help='path to the config used to create the run'
    )
    parser.add_argument(
        '--p',
        help='path override for manual running'
    )
    parser.add_argument(
        '--start_im',
        type=int,
        help='Specify a start image through command line.'
    )
    return parser.parse_args()


def reconstruct_backup(base_path, scan_no, im_dim, im_num, all_dir):
    max_proc = -1
    backup_dir = os.path.join(base_path, str(im_num + scan_no), PROC_OUT_DIR)
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    out_dir = os.path.join(base_path, str(im_num + scan_no), RECON_OUT_DIR)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    for fp in os.listdir(backup_dir):
        rank = int(fp.split('.')[0])
        if rank > max_proc:
            max_proc = rank
    max_proc += 1
    print(f'Found max rank: {max_proc}')

    dims = {}
    avail_datasets = []
    with h5py.File(os.path.join(backup_dir, f'0.hd5'), 'r') as h5_f:
        for ds_path in DATASETS:
            if ds_path in h5_f:
                dims[ds_path] = h5_f[ds_path].shape
                avail_datasets.append(ds_path)
    
    

    raw_ds = {}
    for ds_path in avail_datasets:
        if len(dims[ds_path]) == 1:
            raw_ds[ds_path ]= np.zeros((dims[ds_path][0] * max_proc,))
        
        elif len(dims[ds_path]) == 2:
            raw_ds[ds_path]= np.zeros((dims[ds_path][0] * max_proc, dims[ds_path][1]))

        else:
            raise NotImplementedError(f'New dim! {len(dims[ds_path])}')


    print('Constructing ind')
    num_splits = int(math.sqrt(max_proc))
    print(f'Calculated {num_splits} splits')
    grid_size = im_dim // num_splits

    assert (im_dim % num_splits) == 0

    ind = []
    for i in range(max_proc):
        start_x, start_y = np.divmod(i, num_splits)
        start_x *= grid_size
        start_y *= grid_size

        ind_rows = []
        for i in range(start_x, start_x + grid_size):
            ind_rows.append(np.column_stack(
                (np.full(grid_size, i),
                np.arange(start_y, start_y + grid_size))
            ))
        ind_grid = np.concatenate(ind_rows)
        ind.append(ind_grid)
    ind = np.concatenate(ind)


    print('Gathering proc data')
    for i in range(max_proc):
        with h5py.File(os.path.join(backup_dir, f'{i}.hd5'), 'r') as h5_f_in:
            for ds_path in avail_datasets:
                if len(dims[ds_path]) == 1:
                    raw_ds[ds_path][i * dims[ds_path][0] : (i + 1) * dims[ds_path][0]] = np.array(h5_f_in[ds_path])

                elif len(dims[ds_path]) == 2:
                    raw_ds[ds_path][i * dims[ds_path][0] : (i + 1) * dims[ds_path][0], :] = np.array(h5_f_in[ds_path])
    
    reshapes = {}
    for ds_path in avail_datasets:
        if len(dims[ds_path]) == 1:
            reshapes[ds_path]= np.zeros((im_dim, im_dim))

        elif len(dims[ds_path]) == 2:
            reshapes[ds_path] = np.zeros((im_dim, im_dim, dims[ds_path][1]))


    print('Starting reshape placement')
    #TODO: Could be done faster with broadcast
    for i in range(raw_ds[avail_datasets[0]].shape[0]):
        for ds_path in avail_datasets:
            if len(dims[ds_path]) == 1:
                reshapes[ds_path][ind[i][0], ind[i][1]] = raw_ds[ds_path][i]
            
            elif len(dims[ds_path]) == 2:
                reshapes[ds_path][ind[i][0], ind[i][1], :] = raw_ds[ds_path][i]

    for ds_path in avail_datasets:
        if len(dims[ds_path]) == 2:
            reshapes[ds_path] = np.swapaxes(reshapes[ds_path], 0, 2)
            reshapes[ds_path] = np.swapaxes(reshapes[ds_path], 1, 2)

    print('Writing out')
    with h5py.File(os.path.join(out_dir, f'im_{im_num}_r{scan_no}.hd5'), 'w') as h5_f_out:
        for ds_path in avail_datasets:
            h5_f_out.create_dataset(ds_path, data=reshapes[ds_path])
    
    shutil.copy2(os.path.join(out_dir, f'im_{im_num}_r{scan_no}.hd5'), os.path.join(all_dir, f'im_{im_num}_r{scan_no}.hd5'))

def recon_manual_from_config(config_fp, path_override, override_start=None):
    conf_file, conf_comp, conf_geo, conf_algo = cold.config(config_fp)
    dim_y = conf_file['frame'][1] - conf_file['frame'][0]
    dim_x = conf_file['frame'][3] - conf_file['frame'][2]

    if override_start is None:
        scan_start = override_start
    else:
        scan_start = conf_comp['scanstart']

    out_path = os.path.join(path_override, str(scan_start))

    proc_dump_dir = os.path.join(out_path, PROC_OUT_DIR)
    recon_out_dir = os.path.join(out_path, RECON_OUT_DIR)
    all_outs = os.path.join(conf_file['output'], ALL_OUTS)

    if not os.path.exists(recon_out_dir):
        os.makedirs(recon_out_dir)
    if not os.path.exists(all_outs):
        os.makedirs(all_outs)

    if override_start is not None:
        im_num = override_start
    reconstruct_backup(proc_dump_dir, 
                        recon_out_dir,
                        0,
                        dim_y,
                        im_num,
                        all_outs)

def recon_from_config(comm, config_fp, override_start=None):
    mpi_rank = comm.Get_rank()
    conf_file, conf_comp, conf_geo, conf_algo = cold.config(config_fp)
    dim_y = conf_file['frame'][1] - conf_file['frame'][0]
    dim_x = conf_file['frame'][3] - conf_file['frame'][2]

    if dim_y != dim_x:
        raise NotImplementedError("Can only reconstruct square images!")

    base_path = conf_file['output']
    all_outs = os.path.join(conf_file['output'], ALL_OUTS)

    if mpi_rank == 0:
        if not os.path.exists(all_outs):
            os.makedirs(all_outs)
    comm.Barrier()

    im_num = mpi_rank + conf_comp['scanstart']
    if override_start is not None:
        im_num = mpi_rank + override_start

    if mpi_rank < conf_comp['scannumber']:
        reconstruct_backup(base_path, 
                           mpi_rank,
                           dim_y,
                           im_num,
                           all_outs)


if __name__ == '__main__':
    args = parse_args()
    if args.p is not None:
        recon_manual_from_config(args.config_fp, args.p, args.start_im)
    
    else:
        from mpi4py import MPI
        comm = MPI.COMM_WORLD
        try:
            recon_from_config(comm, args.config_fp, args.start_im)
        except Exception as e:
            import traceback
            with open('err_recon.log', 'a+') as err_f:
                err_f.write(str(e) + '\n') # MPI term output can break.
                err_f.write('Traceback: \n')
                err_f.write(traceback.format_exc())
            comm.Abort(1) # Term run early to prevent hang.
