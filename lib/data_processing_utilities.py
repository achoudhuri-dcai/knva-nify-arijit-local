import inspect

# To turn column indexes into names. Will remove multi-indexing.
# Usage: mydata = colnames_from_index(mydata)
def colnames_from_index(INPUT_DF):
   cols = list(INPUT_DF)
   cols_new = []
   for item in cols:
      if type(item) == str:   # Columns that already have names will be strings. Use unchanged.
         cols_new.append(item)
      else:   # Columns that are indexed or multi-indexed will appear as tuples. Turn them into strings joined by underscores.
         cols_new.append('_'.join(str(i) for i in item))   # Convert each element of tuple to string before joining. Avoids error if an element is nan.

   # Write dataframe with new column names
   dfmod = INPUT_DF
   dfmod.columns = cols_new
   return dfmod

# To clean up column names in a dataframe
# Usage: mydata = clean_colnames(mydata)
def cleancolnames(INPUT_DF):
	# Comments inside the statement create errors. Putting all comments at the top.
	# Convert to lowercase
	# Strip leading and trailing spaces, then replace spaces with underscore
	# Replace slashes, parenthesis, and brackets with underscore
	# Replace some special characters with underscore
	# Replace other special characters with words
	dfmod = INPUT_DF
	dfmod.columns = dfmod.columns.astype(str)  # Convert to string
	dfmod.columns = dfmod.columns.str.lower() \
		.str.strip().str.replace(' ', '_', regex=False) \
		.str.replace('/', '_', regex=False).str.replace('\\', '_', regex=False) \
		.str.replace('(', '_', regex=False).str.replace(')', '_', regex=False) \
		.str.replace('[', '_', regex=False).str.replace(']', '_', regex=False) \
		.str.replace('{', '_', regex=False).str.replace('}', '_', regex=False) \
		.str.replace('!', '_', regex=False).str.replace('?', '_', regex=False) \
		.str.replace('-', '_', regex=False).str.replace('+', '_', regex=False) \
		.str.replace('^', '_', regex=False).str.replace('*', '_', regex=False) \
		.str.replace('.', '_', regex=False).str.replace(',', '_', regex=False) \
		.str.replace('|', '_', regex=False).str.replace('#', '_', regex=False) \
		.str.replace('>', '_gt_', regex=False) \
		.str.replace('<', '_lt_', regex=False) \
		.str.replace('=', '_eq_', regex=False) \
		.str.replace('@', '_at_', regex=False) \
		.str.replace('$', '_dol_', regex=False) \
		.str.replace('%', '_pct_', regex=False) \
		.str.replace('&', '_and_', regex=False)
	return dfmod

# To get the name of an object, as a string
# Usage: object_name = getobjectname(my_object)
# This does not work when getobjectname() is defined in a separate module,
# as it doesn't have access to globals() from the main module.
def getobjectname(OBJECT):
    try:
        objectname = OBJECT.__name__    # If object has a name attribute, use it
    except:
        try:
            objectname = [x for x in globals() if globals()[x] is OBJECT][0]    # Check globals
            objectname = [x for x in locals() if locals()[x] is OBJECT][0]      # Check locals
        except:
            objtype = str(type(OBJECT))
            objectname = f"Unnamed {objtype}"
    return objectname

# To print df.info() with header for readability, and optionally write data info to text file
# Usage: datainfo(mydata)
def datainfo(
        INPUT_DF
        ,MAX_COLS:int=None      # Maximum number of columns to print out. None: will use all columns in data.
        ,OUTFOLDER:str=None     # Folder to output {dataname}_info.txt. None: no file will be created.
    ):
    funcname = inspect.currentframe().f_code.co_name

    # Get data attributes
    dataname = getobjectname(INPUT_DF)
    rowcount = INPUT_DF.shape[0]
    colcount = INPUT_DF.shape[1]
    idxcols = str(list(INPUT_DF.index.names))

    # Print info with header and footer
    pw = 50     # Print width

    print(' ')
    print('=========' + '='*pw)
    print(funcname.upper())
    print('=========' + '='*pw)
    print(f"Name:    {dataname :>{pw}}")
    print(f"Rows:    {rowcount :>{pw},}")
    print(f"Columns: {colcount :>{pw},}")
    print(f"Index:   {idxcols  :>{pw}}")
    print('---------' + '-'*pw)

    if MAX_COLS:
        show_cols = MAX_COLS
    else:
        show_cols = INPUT_DF.shape[1]
    INPUT_DF.info(max_cols=show_cols)

    print('---------' + '-'*pw)
    print(f"End:     {dataname :>{pw}}")
    print('=========' + '='*pw + '\n')

    # Write outputs
    if OUTFOLDER:     # If something has been passed to OUTFOLDER parameter
        filename = f"{dataname}_info"
        print(f"\n<{funcname}> Creating file {OUTFOLDER}\\{filename}.txt")
        datetimestamp = 'Created on ' + time.strftime('%Y-%m-%d %X', time.gmtime()) + ' UTC' + '\n'
        buffer = io.StringIO()
        INPUT_DF.info(buf=buffer, max_cols=colcount)
        filecontents = header + divider + datetimestamp + buffer.getvalue()
        tofile = os.path.join(OUTFOLDER, f"{filename}.txt")
        with open(tofile, 'w', encoding='utf-8') as f:
            f.write(filecontents)
        print(f"<{funcname}> ...done.")

    return None
