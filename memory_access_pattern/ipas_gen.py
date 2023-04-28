import sys
import struct
import lzma
"""
Given trace file, this program generates compressed file with only IP and Access Address in each record.
"""

if __name__=="__main__":
    # * The record structure.
    trace_format="Q2B2B4B2Q4Q"
    out_format="2Q"
    in_rec_len=struct.calcsize(trace_format)
    out_rec_len=struct.calcsize(out_format)

    # * Argument checking.
    if (len(sys.argv)!=3
        or not sys.argv[1].endswith('.champsimtrace.xz')
        or not sys.argv[2].endswith('.ipas.xz')
        ):
        print('Enter .champsimtrace.xz file and output .ipas.xz file')
        exit(1)

    # * Opening xz files.
    with lzma.open(sys.argv[1],"rb") as trace_file,\
        lzma.open(sys.argv[2],"wb") as out:

        # * Find how many bytes the uncompressed trace file will have.
        sz=trace_file.seek(0,2)
        trace_file.seek(0)

        count_=0
        # * How much is 1% of all records.
        count_max=sz//(in_rec_len*100)
        print("0%")
        while (instr_bytes := trace_file.read(in_rec_len)):
            input_instr=struct.unpack(trace_format,instr_bytes)
            ip=input_instr[0]

            # * If 1% of work got over, update the output.
            if count_==count_max:
                count_=0
                sys.stdout.write("\033[F")
                print(trace_file.tell()*100//sz,"%")
            count_+=1

            # * The record's memory accesses are in input_instr[9:].
            # * It is valid only if non-zero.
            for x in input_instr[9:]:
                if x!=0:
                    out_bytes=struct.pack(out_format,ip,x)
                    out.write(out_bytes)
        sys.stdout.write("\033[F")
        print('100%')