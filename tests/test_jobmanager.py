#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function

import os
import sys
import time
import signal
import multiprocessing as mp
import numpy as np
import traceback
import socket
import subprocess
import signal

from os.path import abspath, dirname, split
# Add parent directory to beginning of path variable
sys.path = [split(dirname(abspath(__file__)))[0]] + sys.path

from jobmanager import jobmanager, progress

AUTHKEY = 'testing'
PORT = 42525
SERVER = socket.gethostname()


def test_Signal_to_SIG_IGN():
    global PORT
    PORT += 1
    def f():
        jobmanager.Signal_to_SIG_IGN()
        print("before sleep")
        while True:
            time.sleep(1)
        print("after sleep")

        
    p = mp.Process(target=f)
    p.start()
    time.sleep(0.2)
    assert p.is_alive()
    print("[+] is alive")

    print("    send SIGINT")
    os.kill(p.pid, signal.SIGINT)
    time.sleep(0.2)
    assert p.is_alive()
    print("[+] is alive")
    
    print("    send SIGTERM")
    os.kill(p.pid, signal.SIGTERM)
    time.sleep(0.2)
    assert p.is_alive()
    print("[+] is alive")
    
    print("    send SIGKILL")
    os.kill(p.pid, signal.SIGKILL)
    time.sleep(0.2)
    assert not p.is_alive()
    print("[+] terminated")
    
def test_Signal_to_sys_exit():
    global PORT
    PORT += 1
    def f():
        jobmanager.Signal_to_sys_exit()
        while True:
            try:
                time.sleep(10)
            except SystemExit:
                print("[+] caught SystemExit, keep running")
            else:
                return
        
    p = mp.Process(target=f)
    p.start()
    time.sleep(0.2)
    assert p.is_alive()
    print("[+] is alive")

    print("    send SIGINT")
    os.kill(p.pid, signal.SIGINT)
    time.sleep(0.2)
    assert p.is_alive()
    print("[+] is alive")
    
    print("    send SIGTERM")
    os.kill(p.pid, signal.SIGTERM)
    time.sleep(0.2)
    assert p.is_alive()
    print("[+] is alive")
    
    print("    send SIGKILL")
    os.kill(p.pid, signal.SIGKILL)
    time.sleep(0.2)
    assert not p.is_alive()
    print("[+] terminated")
    
def test_Signal_to_terminate_process_list():
    global PORT
    PORT += 1
    def child_proc():
        jobmanager.Signal_to_sys_exit()
        try:
            time.sleep(10)
        except:
            err, val, trb = sys.exc_info()
            print("PID {}: caught Exception {}".format(os.getpid(), err))
            
    def mother_proc():
        n = 3
        p = []
        for i in range(n):
            p.append(mp.Process(target=child_proc))
            p[-1].start()
            
        jobmanager.Signal_to_terminate_process_list(p)
        print("spawned {} processes".format(n))        
        for i in range(n):
            p[i].join()
        print("all joined, mother ends gracefully")
            
    p_mother = mp.Process(target=mother_proc)
    p_mother.start()
    time.sleep(0.5)
    print("send SIGINT")
    os.kill(p_mother.pid, signal.SIGINT)
    

 
def start_server(n, read_old_state=False, verbose=1):
    print("START SERVER")
    args = range(1,n)
    with jobmanager.JobManager_Server(authkey      = AUTHKEY,
                                      port         = PORT,
                                      verbose      = verbose,
                                      msg_interval = 1,
                                      fname_dump   = 'jobmanager.dump') as jm_server:
        if not read_old_state:
            jm_server.args_from_list(args)
        else:
            jm_server.read_old_state()
        jm_server.start()
    
def start_client(verbose=1):
    print("START CLIENT")
    jm_client = jobmanager.JobManager_Client(server = SERVER, 
                                             authkey = AUTHKEY, 
                                             port    = PORT, 
                                             nproc   = 0,
                                             verbose = verbose)
    jm_client.start()
    if verbose > 1:
        print("jm_client returned")    

def test_jobmanager_basic():
    """
    start server, start client, process trivial jobs, quit
    
    check if all arguments are found in final_result of dump
    """
    global PORT
    PORT += 1
    n = 10
    p_server = mp.Process(target=start_server, args=(n,))
    p_server.start()
    
    time.sleep(1)
     
    p_client = mp.Process(target=start_client)
    p_client.start()
     
    p_client.join(30)
    p_server.join(30)
 
    assert not p_client.is_alive(), "the client did not terminate on time!"
    assert not p_server.is_alive(), "the server did not terminate on time!"
    print("[+] client and server terminated")
     
    fname = 'jobmanager.dump'
    with open(fname, 'rb') as f:
        data = jobmanager.JobManager_Server.static_load(f)
    
    final_res_args_set = {a[0] for a in data['final_result']}
         
    set_ref = set(range(1,n))
     
    intersect = set_ref - final_res_args_set
     
    assert len(intersect) == 0, "final result does not contain all arguments!"
    print("[+] all arguments found in final_results")
    
    
    
def test_jobmanager_server_signals():
    global PORT
    PORT += 1
    print("## TEST SIGTERM ##")
    p_server = mp.Process(target=start_server, args=(30,))
    p_server.start()
    time.sleep(1)
    print("    send SIGTERM")
    os.kill(p_server.pid, signal.SIGTERM)
    assert p_server.is_alive()
    print("[+] still alive (assume shut down takes some time)")
    p_server.join(15)
    assert not p_server.is_alive(), "timeout for server shutdown reached"
    print("[+] now terminated (timeout of 15s not reached)")
    
    fname = 'jobmanager.dump'
    with open(fname, 'rb') as f:
        data = jobmanager.JobManager_Server.static_load(f)    
    
    args_set = data['args_set']
    ref_set = set(range(1,30))
    
    assert len(args_set) == len(ref_set)
    assert len(ref_set - args_set) == 0
    print("[+] args_set from dump contains all arguments")
    
    PORT += 1
    print("## TEST SIGINT ##")    
    p_server = mp.Process(target=start_server, args=(30,))
    p_server.start()
    time.sleep(1)
    print("    send SIGINT")
    os.kill(p_server.pid, signal.SIGINT)
    assert p_server.is_alive()
    print("[+] still alive (assume shut down takes some time)")
    p_server.join(15)
    assert not p_server.is_alive(), "timeout for server shutdown reached"
    print("[+] now terminated (timeout of 15s not reached)")
    
    fname = 'jobmanager.dump'
    with open(fname, 'rb') as f:
        data = jobmanager.JobManager_Server.static_load(f)    
    
    args_set = data['args_set']
    
    ref_set = set(range(1,30))
    assert len(args_set) == len(ref_set)
    assert len(ref_set - args_set) == 0
    print("[+] args_set from dump contains all arguments")
 
    
def test_shutdown_server_while_client_running():
    """
    start server with 1000 elements in queue
    
    start client
    
    stop server -> client should catch exception, but can't do anything, 
        writing to fail won't work, because server went down
    
    check if the final_result and the args dump end up to include
    all arguments given 
    """
    global PORT
    PORT += 1
    
    n = 1000
    
    p_server = mp.Process(target=start_server, args=(n,))
    p_server.start()
    
    time.sleep(1)
    
    PORT += 1
    p_client = mp.Process(target=start_client, args=(2,))
    p_client.start()
    
    time.sleep(2)
    
    os.kill(p_server.pid, signal.SIGTERM)
    
    p_server.join(200)
    p_client.join(200)
    
    try:
        assert not p_server.is_alive()
    except:
        p_server.terminate()
        raise
    
    try:
        assert not p_client.is_alive()
    except:
        p_client.terminate()
        raise
        
    
    
    fname = 'jobmanager.dump'
    with open(fname, 'rb') as f:
        data = jobmanager.JobManager_Server.static_load(f)    

    args_set = data['args_set']
    final_result = data['final_result']

    final_res_args = {a[0] for a in final_result}
        
    set_ref = set(range(1,n))
    
    set_recover = set(args_set) | set(final_res_args)
    
    intersec_set = set_ref-set_recover

    if len(intersec_set) == 0:
        print("[+] no arguments lost!")

    assert len(intersec_set) == 0, "NOT all arguments found in dump!"

def test_shutdown_client():
    shutdown_client(signal.SIGTERM)
    shutdown_client(signal.SIGINT)

def shutdown_client(sig):
    """
    start server with 100 elements in queue
    
    start client
    
    stop client -> client should catch exception, interrupts the running worker function,
        reinsert arguments, client terminates
        
    start client again, continues to work on the queue
    
    if server does not terminate on time, something must be wrong with args_set
    check if the final_result contain all arguments given 
    """
    global PORT
    PORT += 1
    n = 300
    
    print("## terminate client with {} ##".format(progress.signal_dict[sig]))
    
    p_server = mp.Process(target=start_server, args=(n, ))
    p_server.start()
    
    time.sleep(2)
    
    p_client = mp.Process(target=start_client)
    p_client.start()
    
    time.sleep(5)
    
    print("    send {}".format(progress.signal_dict[sig]))
    os.kill(p_client.pid, sig)
    assert p_client.is_alive()
    print("[+] still alive (assume shut down takes some time)")
    p_client.join(5)
    assert not p_client.is_alive(), "timeout for client shutdown reached"
    print("[+] now terminated (timeout of 5s not reached)")
    
    time.sleep(0.5)
     
    p_client = mp.Process(target=start_client)
    p_client.start()
    
    p_client.join(30)
    p_server.join(30)
    
    assert not p_client.is_alive()
    assert not p_server.is_alive()
    
    print("[+] client and server terminated")
    
    fname = 'jobmanager.dump'
    with open(fname, 'rb') as f:
        data = jobmanager.JobManager_Server.static_load(f)    
    
    assert len(data['args_set']) == 0
    print("[+] args_set is empty -> all args processed & none failed")
    
    final_res_args_set = {a[0] for a in data['final_result']}
         
    set_ref = set(range(1,n))
     
    intersect = set_ref - final_res_args_set
     
    assert len(intersect) == 0, "final result does not contain all arguments!"
    print("[+] all arguments found in final_results")

def test_check_fail():
    global PORT
    PORT += 1
    class Client_Random_Error(jobmanager.JobManager_Client):
        def func(self, args, const_args, c, m):
            c.value = 0
            m.value = -1
            fail_on = [3,23,45,67,89]
            time.sleep(0.1)
            if args in fail_on:
                raise RuntimeError("fail_on Error")
            return os.getpid()

    
    n = 100
    verbose=2
    p_server = mp.Process(target=start_server, args=(n,))
    p_server.start()
    
    time.sleep(1)
    
    print("START CLIENT")
    jm_client = Client_Random_Error(server=SERVER, 
                                    authkey=AUTHKEY,
                                    port=PORT, 
                                    nproc=0, 
                                    verbose=verbose)
    
    p_client = mp.Process(target=jm_client.start)
    p_client.start()
    
    try:
        assert p_server.is_alive()
        assert p_client.is_alive()
    except:
        p_client.terminate()
        p_server.terminate()
        raise
    
    print("[+] server and client running")
    
    p_server.join(60)
    p_client.join(60)
    
    assert not p_server.is_alive()
    assert not p_client.is_alive()
    
    print("[+] server and client stopped")
    
    fname = 'jobmanager.dump'
    with open(fname, 'rb') as f:
        data = jobmanager.JobManager_Server.static_load(f)    

    
    set_ref = set(range(1,n))
    
    print(data['args_set'])
    print(data['fail_set'])
    
    assert data['args_set'] == data['fail_set']
    
    final_result_args_set = {a[0] for a in data['final_result']}
    
    all_set = final_result_args_set | data['fail_set']
    
    assert len(set_ref - all_set) == 0, "final result union with reported failure do not correspond to all args!" 
    print("[+] all argumsents found in final_results | reported failure")

def test_jobmanager_read_old_stat():
    """
    start server, start client, start process trivial jobs,
    interrupt in between, restore state from dump, finish.
    
    check if all arguments are found in final_result of dump
    """
    global PORT
    PORT += 1
    n = 100
    p_server = mp.Process(target=start_server, args=(n,))
    p_server.start()
    
    time.sleep(1)
     
    p_client = mp.Process(target=start_client)
    p_client.start()
    
    time.sleep(3)
    
    p_server.terminate()
     
    p_client.join(10)
    p_server.join(10)
 
    assert not p_client.is_alive(), "the client did not terminate on time!"
    assert not p_server.is_alive(), "the server did not terminate on time!"
    print("[+] client and server terminated")
    
    time.sleep(2)
    PORT += 1
    p_server = mp.Process(target=start_server, args=(n,True))
    p_server.start()
    
    time.sleep(2)
     
    p_client = mp.Process(target=start_client)
    p_client.start()

    p_client.join(30)
    p_server.join(30)
 
    assert not p_client.is_alive(), "the client did not terminate on time!"
    assert not p_server.is_alive(), "the server did not terminate on time!"
    print("[+] client and server terminated")    
     
    fname = 'jobmanager.dump'
    with open(fname, 'rb') as f:
        data = jobmanager.JobManager_Server.static_load(f)
    
    final_res_args_set = {a[0] for a in data['final_result']}
         
    set_ref = set(range(1,n))
     
    intersect = set_ref - final_res_args_set
     
    assert len(intersect) == 0, "final result does not contain all arguments!"
    print("[+] all arguments found in final_results")    
    
def test_hashDict():
    s = set()
    
    d1 = jobmanager.hashDict()
    d1['a'] = 1
    d1['b'] = 2
    s.add(d1)
    
    d2 = jobmanager.hashDict()
    d2['a'] = 2
    d2['b'] = 1
    s.add(d2)
    
    d3 = jobmanager.hashDict()
    d3['a'] = 1
    d3['b'] = 2
    
    assert d3 in s
    
    d3['c'] = 0
    assert not d3 in s
    
def test_hashedViewOnNumpyArray():
    s = set()
    
    a = np.ones(4)
    ah = jobmanager.hashableCopyOfNumpyArray(a)
    
    s.add(ah)
    
    b = np.ones(4, dtype=np.int32)
    bh = jobmanager.hashableCopyOfNumpyArray(b)

    # hash function independent of dtype    
    assert hash(ah) == hash(bh)
    # overwritten equal operator ...
    assert ah == bh
    # ... makes such statements possible!
    assert bh in s
     
    # check if it is truly a copy, not just a view
    b[0] = 2
    assert bh[0] == 1
    
    c = np.ones(5)
    ch = jobmanager.hashableCopyOfNumpyArray(c)
    # different array
    assert not ch in s
    
    # check if shape is included in hash calculation
    bh2 = bh.reshape((2,2))
    assert bh2 not in s
    
    # just some redundant back conversion an checking  
    bh2 = bh2.reshape((4,))
    assert bh2 in s

def test_client_status():
    global PORT
    PORT += 1
    n = 10
    p_server = mp.Process(target=start_server, args=(n,False,0))
    p_server.start()
    
    time.sleep(1)
    
    class Client_With_Status(jobmanager.JobManager_Client):
        def func(self, args, const_args, c, m):
            m.value = 100
            for i in range(m.value):
                c.value = i+1
                time.sleep(0.05)

            return os.getpid()

    client = Client_With_Status(server = SERVER, 
                                authkey = AUTHKEY,
                                port    = PORT, 
                                nproc   = 4, 
                                verbose = 1)
    client.start()
    p_server.join()
    
def test_jobmanager_local():
    global PORT
    PORT += 1
    args = range(1,200)
    with jobmanager.JobManager_Local(client_class = jobmanager.JobManager_Client,
                                     authkey = AUTHKEY,
                                     port = PORT,
                                     verbose = 1,
                                     verbose_client=0,
                                     ) as jm_server:
        jm_server.args_from_list(args)
        jm_server.start()
        
def test_start_server_on_used_port():
    global PORT
    PORT += 1
    def start_server():
        const_arg = None
        arg = [10,20,30]
        with jobmanager.JobManager_Server(authkey = AUTHKEY,
                                          port    = PORT, 
                                          const_arg=const_arg,
                                          fname_dump=None) as server:
            server.args_from_list(arg)
            server.start()
            
    def start_server2():
        const_arg = None
        arg = [10,20,30]
        with jobmanager.JobManager_Server(authkey=AUTHKEY,
                                          port = PORT, 
                                          const_arg=const_arg,
                                          fname_dump=None) as server:
            server.args_from_list(arg)
            server.start()
            
    p1 = mp.Process(target=start_server)
    p1.start()
    
    time.sleep(1)
    
    other_error = False
    
    try:
        start_server2()
    except (RuntimeError, OSError) as e:
        print("caught Exception '{}' {}".format(type(e).__name__, e))
    except:
        other_error = True
    
    time.sleep(1)
    p1.terminate()
    time.sleep(1)
    p1.join()    
    
    assert not other_error
        
def test_shared_const_arg():
    global PORT
    PORT += 1
    def start_server():
        const_arg = {1:1, 2:2, 3:3}
        arg = [10,20,30]
        with jobmanager.JobManager_Server(authkey=AUTHKEY,
                                          port = PORT, 
                                          const_arg=const_arg,
                                          fname_dump=None) as server:
            server.args_from_list(arg)
            server.start()
            
        print("const_arg at server side", const_arg)
            
    def start_client():
        class myClient(jobmanager.JobManager_Client):
            @staticmethod
            def func(arg, const_arg):
                const_arg[os.getpid()] = os.getpid() 
                print(os.getpid(), arg, const_arg)
                return None
            
        client = myClient(server=SERVER,
                          authkey=AUTHKEY,
                          port = PORT,
                          nproc=1,
                          verbose=2)
        
        client.start()
            
    PORT += 1
    p1 = mp.Process(target=start_server)
    p2 = mp.Process(target=start_client)
    
    p1.start()
    
    time.sleep(1)
    
    p2.start()
    
    p2.join()
    
    time.sleep(1)
    p1.join()
    
def test_digest_rejected():
    global PORT
    PORT += 1
    n = 10
    p_server = mp.Process(target=start_server, args=(n,False,0))
    p_server.start()
    
    time.sleep(1)
    
    class Client_With_Status(jobmanager.JobManager_Client):
        def func(self, args, const_args, c, m):
            m.value = 100
            for i in range(m.value):
                c.value = i+1
                time.sleep(0.05)

            return os.getpid()

    client = Client_With_Status(server = SERVER, 
                                authkey = AUTHKEY+' not the same',
                                port    = PORT, 
                                nproc   = 4, 
                                verbose = 2)
    try:
        client.start()
    except ConnectionError as e:
        print("Not an error: caught '{}' with message '{}'".format(e.__class__.__name__, e))
        p_server.terminate()
        
    p_server.join()            
    
def test_exception():   
    global PORT
    PORT += 1 
    class MyManager_Client(jobmanager.BaseManager):
        pass
        
    def autoproxy_server(which_python, port, authkey, outfile):
        if which_python == 2:
            python_interpreter = "python2.7"
            python_env = {"PYTHONPATH": "/usr/lib/python2.7"}
        elif which_python == 3:
            python_interpreter = "python3.4"
            python_env = {"PYTHONPATH": "/usr/lib/python3.4"}
        else:
            raise ValueError("'which_python' must be 2 or 3")
            
        
        path = dirname(abspath(__file__))
        cmd = [python_interpreter,
               "{}/start_autoproxy_server.py".format(path),
               str(port), 
               authkey]

        print(cmd)
        return subprocess.Popen(cmd, env=python_env, stdout=outfile, stderr=subprocess.STDOUT)

    def autoproxy_connect(server, port, authkey):
        MyManager_Client.register('get_q')
        
        m = MyManager_Client(address = (server, port),                              
                             authkey = bytearray(authkey, encoding='utf8'))
        
        jobmanager.call_connect(m.connect, dest = jobmanager.address_authkey_from_manager(m), verbose=1)
        
        return m
        
    for p_version_server in [2, 3]:
        PORT += 10
        port = PORT
        authkey = 'q'
        with open("ap_server.out", 'w') as outfile:
            
            p_server = autoproxy_server(p_version_server, port, authkey, outfile)
            print("autoproxy server running with PID {}".format(p_server.pid))
            time.sleep(1)
            
            print("running tests ...")
            print()
             
            try:
                try:
                    autoproxy_connect(server=SERVER, port=port, authkey=authkey)
                except jobmanager.RemoteValueError:
                    if (sys.version_info[0] == 3) and (p_version_server == 2):
                        print("that is ok")      # the occurrence of this Exception is normal
                        pass
                    else:                
                        raise                    # reraise exception
                except ValueError:
                    if (sys.version_info[0] == 2) and (p_version_server == 3):
                        print("that is ok")      # the occurrence of this Exception is normal
                        pass
                    else:                
                        raise                    # reraise exception

                # all the following only for the same python versions
                if (sys.version_info[0] != p_version_server):
                    continue
                    
                try:
                    autoproxy_connect(server=SERVER, port=port+1, authkey=authkey)
                except jobmanager.JMConnectionRefusedError:
                    print("that is ok")
                except:
                    raise
                
                try:
                    autoproxy_connect(server=SERVER, port=port, authkey=authkey+'_')
                except jobmanager.AuthenticationError:
                    print("that is ok")
                except:
                    raise
                
                m = autoproxy_connect(server=SERVER, port=port, authkey=authkey)
                
                q = m.get_q()
                
                q_get = jobmanager.proxy_operation_decorator_python3(q, 'get')
                q_put = jobmanager.proxy_operation_decorator_python3(q, 'put')
                
                s1 = 'hallo welt'
                q_put(s1)
                s2 = q_get()
                
                assert s1 == s2
                
                
                
                
            finally:
                print()
                print("tests done! terminate server ...".format())
                
                p_server.send_signal(signal.SIGTERM)
                
                t = time.time()
                timeout = 10
                r = None
                while r is None:
                    r = p_server.poll()
                    time.sleep(1)
                    print("will kill server in {:.1f}s".format(timeout - (time.time() - t)))
                    if (time.time() - t) > timeout:
                        print("timeout exceeded, kill p_server")
                        print("the managers subprocess will still be running, and needs to be killed by hand")
                        p_server.send_signal(signal.SIGKILL)
                        break
                
                print("server terminated with exitcode {}".format(r))
 
        
    

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pass
    else:    
        func = [
#         test_Signal_to_SIG_IGN,
#         test_Signal_to_sys_exit,
#         test_Signal_to_terminate_process_list,
#                 
#         test_jobmanager_basic,
#         test_jobmanager_server_signals,
#         test_shutdown_server_while_client_running,
#         test_shutdown_client,
#         test_check_fail,
#         test_jobmanager_read_old_stat,
#         test_hashDict,
#         test_hashedViewOnNumpyArray,
#         test_client_status,
#         test_jobmanager_local,
#         test_start_server_on_used_port,
#         test_shared_const_arg,
#         test_digest_rejected,
        test_exception,

        lambda : print("END")
        ]
        for f in func:
            print()
            print('#'*80)
            print('##  {}'.format(f.__name__))
            print()
            f()
            time.sleep(1)
    

#         _test_interrupt_client()
    
