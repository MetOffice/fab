Work Queue
##########

At the abstract level, a build system is just a means of managing a
:abbr:`Directed Acyclic Graph (DAG)` of build operations. Compilation of source
code cannot happen before that source code is preprocessed or before all the
modules it uses have been compiled.

Managing that graph explicitly is a complicated business so it is generally
managed behind the scenes. For instance Make's target and prerequisite approach
specifies the relationships but the user doesn't have to touch the graph.

The "work queue" allows the graph to be emergent behaviour of the
implementation, thereby insulating the user and developer from it.

In this model each task in the build is performed by a stand-alone task. These
tasks are stored in a :abbr:FIFO (First In, First Out) queue. A task farm of
workers then pop tasks off the front of the queue and check to see if they can
be run. That is, that all their prerequisites are met. If not then they are
pushed on to the back of the queue for reconsideration later, after they have
done a full lap of the queue.

Tasks which are ready are run. Running the task may produce new tasks which go
back on the queue for consideration later.

Basic Work Queue Operation
++++++++++++++++++++++++++

An example may prove illuminating.

.. mermaid::

   timeline
      title Work Queue Over Time
      T0 : Compile program.f90
         : Link program
         : Preprocess messy.F90
         : Compile simple_mod.f90
      T1 : Link program
         : Preprocess messy_mod.F90
         : Compile simple_mod.f90
         : Compile program.f90
      T2 : Preprocess messy_mod.F90
         : Compile simple_mod.f90
         : Compile program.f90
         : Link program
      T3 : Compile simple_mod.f90
         : Compile program.f90
         : Link program
         : Compile messy_mod.f90
      T4 : Compile program.f90
         : Link program
         : Compile messy_mod.f90
      T5 : Link program
         : Compile messy_mod.f90
         : Compile program.f90
      T6 : Compile messy_mod.f90
         : Compile program.f90
         : Link program
      T7 : Compile program.f90
         : Link program
      T8 : Link program

Let's walk though what this diagram shows.

At time "T0" there are four actions on the queue. The first is "Compile
``program.f90``." It depends on ``simple_mod`` and ``messy_mod`` which have
not yet been compiled so it cannot run. It is put onto the back of the queue.

Time "T1" finds "Link program" at the head of the queue. Clearly that cannot
run so it is put on the back of the queue.

Next step (T2) and "Preprocessing ``messy_mod.F90``" has come up to the
surface. This doesn't depend on anything so it can be executed, the result
being "Compile ``messy_mod.f90``" which is put on the back of the queue.

With T3, "Compile ``simple_mod.f90``" is at the top. It can also be executed
straight away as there are no prerequisites. It doesn't produce any work so
nothing goes on the queue and it shrinks.

T4 sees us back at the start with "Compile ``program.f90``" at the head. The
result of the previous step is a prerequisite which is now satisfied but
``messy_mod.f90`` has not yet been compiled so once again the program cannot
be compiled. Back on the queue it goes.

Also waiting for prerequisites is "Link program" which comes to the top in T5.

Bubbling up in T6 is "Compile ``messy_mod.f90``" which is executed and the
queue shrinks again.

Now, in T7, "Compile ``program.f90``" may be executed as all its prerequisites
are now satisfied. The queue shrinks once more.

Finally in T8 the program may be linked and the queue is emptied.

Notice how the :abbr:`DAG (Directed, Acyclic Graph)` has been traversed without
ever having to reason about it directly.

Also notice that an action may be performed the moment its prerequisites are
satisfied. This opens up the possibility of building and running unit tests
as the source is compiled rather than as a separate step. In turn, this makes
it possible to halt compilation the moment a test fails.

This may lead to a faster turn-around in development since continuing to
compile after a failure is found may not be worth the effort.

Because tasks may be performed the moment they are ready there is no need to
split the over-all build process into phases. This improves parallel efficiency
as phasing represents a barrier at which parallel threads must wait, leaving
them spinning.

Everything Is A Task
++++++++++++++++++++

Part of the power of this approach is the number of activities performed by a
build system which can be encompassed by the concept of "task."

Tasks aren't limited to creating one or two new tasks on completion, this means
the process of walking a file tree looking for source can be a task which
generates potentially hundreds of compilation tasks.

Tasks are also not required to be short lived. Once a program entry point is
found a long lived task may be generated which repeatedly attempts to determine
all the prerequisites for a link. Such a task cannot continue until all the
source files involved have been prepared and analysed so it will likely exist
on the queue for some time.

Stall Detection
+++++++++++++++

One complication of using a work queue with a task farm is that in the real
world we can't be guaranteed the DAG is fully traversable. There may be nodes
where the prerequisites are never satisfied.

As such we need a means to identify when the queue has stalled and kill it when
it does.

This is achieved by injecting a special "task" onto the work queue called a
"sentinel." Each time a worker completes a task it increments a counter. When
it reaches a sentinel it checks the counter to see how much work has been done.

If it is not zero, the queue has not stalled so the counter is reset to zero
and the sentinel returned to the queue for another go round. If it is zero then
the queue has stalled and the worker dies.

Of course, in a threaded environment with multiple workers there is a potential
race condition. Just because no work has been completed (the counter is zero)
when a worker encounters the sentinel and checks doesn't mean that one of the
pieces of work being performed by another worker wont complete and increment
the counter.

To handle this we introduce additional sentinels, one per worker, and when the
worker retrieves one from the queue it enters a barrier. This synchronises all
the workers on the sentinel and ensures that all work is complete before the
stall check is made.

The down side of this is that it introduces a synchronisation point which, by
necessity, stalls the parallelism for a period. The workers in the barrier are
spinning, not progressing any work.

Optimising Queue Entry
++++++++++++++++++++++

In the basic implementation new tasks are pushed onto the back of the queue and
must wait a full cycle of the queue before they can be considered for
execution.

This gives correct behaviour but often a new task is ready to run straight
away. Therefore a potential optimisation is to put new tasks on the front of
the queue so they may be considered immediately.

Tasks which are being requeued due to being unable to run still go on the
back of the queue. We need a full cycle of the queue before considering
them again. The action which frees up their prerequisites may be in the
queue so by the time they come round again these prerequisites may have
completed.

A potential problem with this optimisation comes as the sentinels approach the
front of the queue. One worker may recover a sentinel and enter the barrier,
temporarily removing it from the worker pool. Meanwhile the other workers can
continue to process tasks and generate new work for an arbitrary period of time
before finally reaching their sentinels.

Some profiling work is needed to quantify this problem and potential mitigation
strategies should be considered.

One potential option is to disable the "new work to front of queue" mode as
soon as one worker enters the barrier. This potentially solves the immediate
problem but now new work is going on the end of the queue again, the problem we
were trying to solve in the first place. So then we might consider a special
queue where work can be inserted immediately after the sentinels. But this is
adding complexity on complexity to solve a problem we haven't proven exists.

.. note:: These experiments have not been carried out yet, this plot is a
          placeholder.

.. plot::

   from _plots.plot import clustered_bar_plot

   timings = {
       'New work to back': ['00:00', '00:00', '00:00', '00:00', '00:00'],
       'New work to front': ['00:00', '00:00', '00:00', '00:00', '00:00'],
       'New work to front until sentinal, then back': ['00:00', '00:00', '00:00', '00:00', '00:00'],
       'New work to front until sentinal, then after sentinal': ['00:00', '00:00', '00:00', '00:00', '00:00']
   }
   threads = (1, 2, 3, 4, 5)

   clustered_bar_plot(timings,
                      threads, "Threads",
                      "Seconds to complete, lower is better",
                      "Build of Atmosphere application from clean")
