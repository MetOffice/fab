.. _profiling_performance:

Profiling Performance
#####################

Comparing performance of different build system implementations.

Timings are performed on the SPICE back-end in order to have enough threads
available for workers. Our desktop machines only have 2 threads.

The problem is that the SPICE nodes are all shared and the job of building
software is heavily I/O bound. This means other jobs sharing the node can have
a strong effect on performance.

In order to get reliable readings it is necessary to reserve a whole node in
order to get exclusive access to its I/O capability.

.. note::

   The need to reserve whole nodes was not realised until after this page had
   been prepared. Runs with Make and Toy have been rerun. Waiting for a stable
   Baf system to test.

Skeleton
++++++++

Compiling the "Skeleton" application from the LFRic core repository.

.. plot::

   from _plots.plot import clustered_bar_plot

   timings = {
       'Make': ['03:32', '02:48', '02:29', '02:24', '02:22'],
       'Baf': ['04:05', '02:38', '01:47', '01:30', '01:19'],
       'Toy': ['2:24', '1:20', '1:02', '0:55', '0:59']
   }
   workers = (1, 2, 3, 4, 5)

   clustered_bar_plot(timings,
                      workers, "Workers",
                      "Minutes to complete, lower is better",
                      "Build of Skeleton application from clean")

This is such a short and simple build it doesn't tell us a whole lot but it is
easy to set up and quick to run. It gives us some confidence that we aren't
wasting our time.

The fact that the performance curve flattens out so quickly and is slower than
Baf at scale is disappointing. The fact that it starts faster is heartening and
it does show that there are potentially optimisations to be made.

Atmosphere
++++++++++

Compiling the full Atmosphere application from LFRic applications repository.

.. plot::

   from _plots.plot import clustered_bar_plot

   timings = {
       'Make': ['37:07', '24:58', '21:47', '20:19', '17:41',
                '00:00', '00:00', '00:00', '00:00', '15:24',
                '00:00', '00:00', '14:55', '00:00', '00:00',
                '15:39'],
       'Baf': ['46:49', '24:29', '18:35', '13:52', '12:01', '00:00', '00:00',
               '00:00', '00:00', '09:12', '00:00', '00:00', '07:43', '00:00',
               '00:00', '06:29'],
       'Toy': ['29:10', '15:03', '10:36', '08:35', '07:33',
               '00:00', '00:00', '00:00', '00:00', '05:41',
               '00:00', '00:00', '04:38', '00:00', '00:00',
               '04:31']
   }
   workers = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)

   clustered_bar_plot(timings,
                      workers, "Workers",
                      "Minutes to complete, lower is better",
                      "Build of Atmosphere application from clean")

What we can see from these plots is that both Baf and Toy build systems are
considerably faster than the current Make based system. A good chunk of this
improvement is likely to be due to parallelism of source analysis. It must be
kept serial in the current build system in order to avoid file locking problems
around a database.

Although the Toy falls more quickly as number of threads increases it would not
be unreasonable to postulate that given a few more cores Baf and Toy will
converge at a common floor. This floor is likely due to the problem of building
software being file bound in the end.

There are two, related, factors which embody the minimum possible floor to
performance. Those are the subprocesses invoked by the build system, PSyclone
and compilation are expected to be the most expensive, and file access.

Any attempt to improve performance will likely have to concentrate on these two
factors.

Oversubscribing and Blocking Operations
+++++++++++++++++++++++++++++++++++++++

X86 processors often make their physical cores appear as a pair of logical
cores. This technology is called "HyperThreading" by Intel or by it's
general term :abbr:`Simultaneous MultiThreading (SMT)` by AMD.

The purpose of this trick is to improve efficiency by making sure that every
computational unit of the core has the best chance to be fully utilised.

Consider a typical desktop system, if a piece of structural stress visualisation
software is hammering the floating point unit (FPU) for finite element analysis
the Arithmetic and Logic Unit (ALU), which handles integer arithmetic, is
sitting idle. With SMT it is possible for "minesweeper", which performs only
integer arithmetic, to steal cycles on the ALU.

The important point here is that there is no additional hardware so the two
logical cores have to share the real hardware. This means if both are trying
to clobber the FPU then they will get only 50% of its capability each.

In light of this we tend to disable this feature for model runs as it is more
likely to hinder than help. On the surface it would seem that the same were
true for build systems, they are going to spend all their time in the ALU so
pretending that we have 2 of them when we only have 1 seems counter productive.

However, there is another factor at play in a build system. They spend a lot of
time going to disc, either to read source files and write object files, or to
load tool executables. Obviously file system caching helps here but it remains
likely that our problem is I/O bound.

This means threads may often be blocked waiting for I/O operations to complete.
In which case a different thread could be making use of the CPU to get some
work done. Of course there's a limit to how useful this can be since a lot of
that alternative work will also block on I/O.

Still, it's worth exploring how much value there is in:

a. Oversubscribing the physical CPU cores
#. Oversubscribing the logical CPU cores

.. note:: These timings seem to be even more susceptible to system noise then
          normal.

.. note:: These timings may not measure what I think they do. It looks like
          the nodes used for testing have SMT disabled.

.. plot::

   from _plots.plot import clustered_bar_plot

   timings = {
       'One physical core': ['29:38', '21:05', '18:49', '16:55', '17:57', '16:48'],
       'Two physical cores': ['32:01', '15:11', '13:09', '12:15', '10:00', '09:55']
   }
   workers = (1, 2, 3, 4, 5, 6)

   clustered_bar_plot(timings,
                      workers, "Workers",
                      "Minutes to complete, lower is better",
                      "Build of Atmosphere application from clean")

In the case where there is one physical core the single worker build maps the
worker to the core. The two worker build makes use of SMT while the 3 and 4
worker builds are pure over-subscription.

When 2 physical cores are available, the 1 worker run is under-subscribed
while the 2 worker run is fully subscribed. Three and 4 worker runs represent
use of SMT while 5 and 6 represent over subscription.

Early in the development of SMT chip designers noted that compared to a
:abbr:`floating-point unit (FPU)` and integer :abbr:`integer/logic unit (ALU)`
takes virtually no space. As such they started throwing extras in so if you are
doing only integer and logic maths (which is largely true for building software)
you do effectively have two hardware threads. This is due to them not fighting
over the shared FPU, which they aren't using.

Recent CPUs have introduced vector ALUs which may also be relevant to building
software.

With all this said, I think the plot shown above makes some sense. We are
apparently getting a worthwhile performance boost out of the "pretend" cores
of SMT because our problem is I/O bound and we may actually have two physical
cores for the work we are doing.

Performance worsens as we increase workers past a certain point, likely because
contention over CPU elements and I/O starts to become an issue.
