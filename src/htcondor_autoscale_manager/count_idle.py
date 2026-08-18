
import classad2 as classad
import htcondor2 as htcondor


def count_idle(resource, pool=None):
    coll = htcondor.Collector(pool)

    pslots = coll.query(htcondor.AdTypes.Startd,
               constraint="GLIDEIN_ResourceName=?=%s && PartitionableSlot && Offline =!= true" % classad.quote(resource),
               projection=["TotalCPUs", "CPUs", "Name"])

    return {"total": len(pslots), "idle": sum(1 for slot in pslots if slot.get("CPUs") == slot.get("TotalCpus"))}
